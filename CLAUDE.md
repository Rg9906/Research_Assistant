# CLAUDE.md — PaperPilot AI Engineering Handbook

This is the permanent engineering reference for this repository. It reflects
the actual state of the code as of the last update (2026-07-18, post
cleanup-pass), not aspirational design. When code and this document
disagree, trust the code and update this document.

## 1. What this project is

PaperPilot AI is an autonomous multi-agent research assistant: discover papers,
rank them, download and index them, and let a user chat with grounded answers.
Full vision and feature roadmap: `ProjectIdea.txt` (repo root) — read it once,
it is the north star for "why" a feature exists.

Core philosophy from that document, still the guiding principle: the LLM is one
component in a system; intelligence comes from planning, retrieval, memory,
reasoning, tools, orchestration, and evaluation — not from prompting a model
harder.

## 2. Repository layout

| Path | Responsibility |
|---|---|
| `src/paperpilot/` | Installable Python package (`pip install -e ".[dev]"`, hatchling). All domain logic lives here. |
| `src/paperpilot/core/models.py` | Pydantic data contracts shared across the whole system: `PaperMetadata`, `TextChunk`, `ExtractedPage`, `ProcessedDocument`, `RetrievalResult`. Every module imports from here — this is the schema layer. |
| `src/paperpilot/config.py` | `Settings` (pydantic-settings), `.env`-backed, `get_settings()` cached singleton. The `.env` path is anchored to the repo root (not the CWD) so running the API from `src/` still picks it up. |
| `src/paperpilot/net.py` | `enable_system_trust_store()` — makes TLS verify against the OS trust store via `truststore`. Required on machines whose antivirus/proxy intercepts TLS, where `certifi` rejects every HTTPS call. Called at the top of `app/api.py`, before anything opens a connection. |
| `src/paperpilot/search/rate_limit.py` | `RateLimiter` — thread-safe minimum-interval pacing for quota-limited APIs (Semantic Scholar). |
| `src/paperpilot/llm/factory.py` | **Single source of truth for "which LLM backend do we talk to."** `resolve_provider_order()` implements the selection policy; `build_chat_model()` returns a LangChain `BaseChatModel` for the agents, `build_llama_llm()` returns a LlamaIndex `LLM` for the RAG stack. Both consume the same ordering, so the two stacks can't drift onto different providers. See §5. |
| `src/paperpilot/document/downloader.py` | `PDFDownloader` — fetch, validate (magic bytes + PyMuPDF open), retry with backoff, scheme allowlist (http/https by default), and a streamed size cap. |
| `src/paperpilot/retrieval/embedder.py` | `EmbeddingEngine` wrapping `sentence-transformers` (MiniLM). Used only by the ranker (see §4). |
| `src/paperpilot/search/` | `providers.py` (arXiv, Semantic Scholar via a `SearchProvider` Protocol), `ranker.py` (weighted scoring), `agent.py` (`SearchAgent`: fetch → dedupe → rank). Solid, well-tested. |
| `src/paperpilot/agent/` | `planner.py`, `tutor.py`, `critic.py` — LangChain `BaseChatModel`-based agents implementing the grounded-QA + self-critique contract, plus `formatting.py` (shared `clean_json_markdown` / `format_chunks_as_context` helpers used by all three). See §4 for their current (disconnected) status. |
| `src/paperpilot/graph/` | `state.py` (`AgentState` TypedDict), `nodes.py` (`AgentNodes`), `builder.py` (LangGraph `StateGraph` + routers). Compiles a planner→search→retrieve→tutor→critic loop. Not wired to the API — see §4. |
| `src/paperpilot/services/grounded_qa.py` | **The production QA path.** `GroundedQAService` joins the two stacks: retrieval via `PaperSessionManager.retrieve_across_papers` (Stack B) → `TutorAgent` → `CriticAgent` → bounded retry (Stack A). `nodes_to_chunks` is the single LlamaIndex→`TextChunk` translation point. See §4. |
| `src/paperpilot/services/summarizer.py` | `SummarizerService` + `SUMMARY_LEVELS` — the ten summary views from `ProjectIdea.txt`, generated through `GroundedQAService` (so summaries are audited too) and cached on disk per paper+level at `storage/papers/paper_<id>/summaries.json`. |
| `src/paperpilot/services/paper_chat/` | **The document-intelligence stack.** `session.py` (`PaperSession`, `PaperSessionManager`, `MultiPaperRetriever`) owns LlamaIndex document loading, chunking, indexing, persistence, single- and multi-paper chat. `exceptions.py` holds the domain exception hierarchy. |
| `src/paperpilot/workspace/manager.py` | `WorkspaceManager` — SQLite (`data/workspace.db`) for workspaces, papers, workspace↔paper mapping, and a legacy `text_chunks` table (vestigial — populated with `chunks=[]` everywhere now that LlamaIndex owns chunk storage on disk). `_get_connection()` is a contextmanager that always closes the connection. |
| `src/paperpilot/pipeline.py` | `DocumentPipeline` — facade over `PaperSessionManager` + `WorkspaceManager`, used by the LangGraph nodes and by metadata sync (`sync_paper_metadata` now calls the public `WorkspaceManager.get_paper_by_id`). |
| `src/app/` | FastAPI backend (`api.py`, `utils.py`). **Not an installed package** — no `__init__.py`. Run from `src/` so `app` resolves as a namespace package, e.g. `uvicorn app.api:app --reload` from inside `src/`. `templates.html` is a static design mockup, never served. |
| `frontend/` | React 19 + Vite + TypeScript + Tailwind (Material-3-style token palette in `tailwind.config.js`). Routes: `/` (DiscoveryFeed — search), `/library` (ResearchLibrary — workspaces, click-through to detail), `/paper/:paperId` (PaperSummary — abstract + tabbed AI views + chat), `/workspace/:workspaceId` (WorkspaceDetail — multi-paper workspace chat). `src/context/AgentActivityContext.tsx` provides real in-flight-request status to the navbar. `src/api/client.ts` is the single fetch layer; base URL is hardcoded to `http://localhost:8000/api`. |
| `tests/` | pytest suite, `pythonpath=src` (see `pyproject.toml`), fully offline — external calls are mocked/stubbed. `tests/test_tutor.py::StubChatModel` is reused across planner/critic/graph tests; keep that pattern. |
| `data/` | Runtime SQLite DB + legacy FAISS indexes. Gitignored. |
| `storage/papers/paper_<uuid>/{index,cache}` | Per-paper LlamaIndex persistence directory (docstore + fingerprint.json). Gitignored. |
| Root `test_search.py`, `create_pdf.py` | Manual/dev scripts (documented as such in their own docstrings), not part of the pytest suite — `test_search.py` hits live network APIs, `create_pdf.py` generates a synthetic fixture PDF. |

## 3. Request flow (production path today)

```
React (DiscoveryFeed) --POST /api/search--> FastAPI
  --> SearchAgent (cached via app/utils.py::get_search_agent)
  --> dedupe (DOI / arXiv id / Jaccard title >= 0.85) --> weighted rank --> results

React (PaperSummary) --POST /api/papers/process--> FastAPI
  --> PaperSessionManager.get_or_create_session   # index BEFORE any DB write
        --> PDFDownloader.download_pdf (http/https only, size-capped)
        --> fingerprint check (sha256 + embed model + chunk params + llama-index version)
        --> [cache hit] load_index_from_storage
        --> [cache miss] PyMuPDFReader -> SentenceSplitter(512/50) -> VectorStoreIndex
                          (embeddings: BAAI/bge-small-en-v1.5) -> persist to storage/
  --> only on success: WorkspaceManager.create_workspace + add_paper_to_workspace

React (chat: PaperSummary or WorkspaceDetail) --POST /api/workspaces/{id}/chat--> FastAPI
  --> WorkspaceManager.get_workspace_papers(id)   # ALL papers in the workspace
  --> [grounded path, default] GroundedQAService.answer(papers, query, history, difficulty)
        --> condense follow-up into a standalone retrieval query (if history)
        --> retrieve_across_papers -> MultiPaperRetriever + similarity cutoff
        --> TutorAgent -> CriticAgent -> retry on rejection
        --> returns answer + citations + approved/refused/attempts
  --> [fallback] PaperSessionManager.chat_across_papers(...)  # LlamaIndex chat engine
  --> WorkspaceChatStore (app/utils.py) persists the returned chat_history,
      scoped per workspace_id — NOT baked into the shared PaperSession

React (PaperSummary tabs) --GET /api/summary-levels--> the 10 level definitions
  --POST /api/papers/{paper_id}/summary/{level_id}[?regenerate=true]--> FastAPI
  --> SummarizerService: disk cache hit (no LLM call) or generate via GroundedQAService
```

## 4. The two stacks, and how they are now joined

There were **two parallel implementations** of "answer a question about a
paper." They are now composed rather than competing — `services/grounded_qa.py`
uses Stack B for retrieval and Stack A for generation + audit:

```
/api/workspaces/{id}/chat
  -> GroundedQAService.answer()
       -> PaperSessionManager.retrieve_across_papers()   # Stack B: index + MultiPaperRetriever
       -> nodes_to_chunks()                              # LlamaIndex -> core.models.TextChunk
       -> TutorAgent.answer_question()                   # Stack A: grounded prompt + refusal string
       -> CriticAgent.evaluate_answer()                  # Stack A: grounding/relevance/style audit
       -> [rejected] retry with feedback, up to rag_max_critique_retries
```

Set `rag_grounded_qa_enabled=false` to fall back to the plain LlamaIndex chat
path, which is still fully wired (`chat_across_papers`). The endpoint also
degrades to it automatically if the agents' chat model can't be built — see
`app/utils.py::get_optional_grounded_qa_service`.

- **Stack A — agents** (`agent/planner.py`, `tutor.py`, `critic.py`). Tutor and
  Critic are now **live in production** via `GroundedQAService`. The `graph/`
  LangGraph pipeline (`compile_agent_graph`) and `planner.py` are still **not
  invoked by any endpoint** — that is the remaining inert piece, and the
  planner is the natural next thing to wire in (§11).

- **Stack B — LlamaIndex session stack** (`services/paper_chat/session.py`).
  The permanent document-intelligence layer: loading, chunking, indexing,
  persistence, and multi-paper retrieval. Applies a similarity-cutoff
  postprocessor (`rag_similarity_threshold`, default 0.7) plus an optional
  reranker. `retrieve_across_papers()` exposes retrieval without generation —
  that is the seam `GroundedQAService` consumes.

**Working agreement going forward:** LlamaIndex (Stack B) owns document
intelligence; the agents own generation and verification. Do not build a third
RAG implementation, and do not add a second retriever — extend
`retrieve_across_papers`/`MultiPaperRetriever` instead.

## 5. Configuration (`src/paperpilot/config.py`)

`Settings` (pydantic-settings, `.env`-backed) — key groups:
- Paths: `data_dir`, `papers_dir`, `index_dir`, `db_path`, `storage_papers_dir`.
- Legacy chunking/ranking embedding: `embedding_model_name` (`all-MiniLM-L6-v2`) — used only by `PaperRanker` for title/abstract similarity scoring, not for paper chat.
- RAG (LlamaIndex, Stack B): `rag_chunk_size`/`rag_chunk_overlap` (512/50), `rag_top_k`, `rag_embedding_model` (`BAAI/bge-small-en-v1.5`), `rag_llm_model` (`gpt-4o-mini`), `rag_similarity_threshold` (0.7 — wired into every session's `node_postprocessors` as a `SimilarityPostprocessor`, applied before the optional reranker), `rag_rerank_enabled`/`rag_rerank_model`/`rag_rerank_top_n`.
- Grounded QA: `rag_grounded_qa_enabled` (default true — route chat through
  Tutor/Critic), `rag_max_critique_retries` (2; each retry costs two more LLM
  calls, so raising it trades latency and money for stricter grounding),
  `rag_critique_enabled` (true; set false on small per-minute token quotas — the
  audit re-sends the full context and roughly doubles tokens per answer).
- **Token budgeting matters more than it looks.** One grounded answer is
  1 tutor + 1 critic call over the same context, ×(1 + retries). Groq's free
  tier (6000 TPM) sustains roughly one summary per minute at
  `rag_summary_top_k=6`. If chat 429s constantly, lower `rag_top_k` /
  `rag_summary_top_k` or set `rag_critique_enabled=false` before assuming a bug.
- Semantic Scholar: `semantic_scholar_rate_limit_rps` (1.0 — the standard key
  grant) and `semantic_scholar_max_retries` (3). Requests are paced client-side
  *and* retried on 429 with exponential backoff; in live testing S2 returns 429
  even when correctly paced, so both halves are load-bearing.
- Summaries: `rag_summary_top_k` (10). Summaries retrieve more widely than chat
  and with the similarity cutoff **disabled** — see §7 for why.
- Search ranking weights: `search_weight_similarity/citations/recency` (auto-normalized to sum to 1 in `PaperRanker.__init__` if they don't), `search_decay_rate`.
- **LLM provider selection (`paperpilot/llm/factory.py`)**: three providers are
  supported — `gemini` (aliases: `google`, `google-genai`), `groq`, `openai` —
  with keys `gemini_api_key`/`groq_api_key`/`openai_api_key` and models
  `gemini_model`/`groq_model`/`llm_model_name` (OpenAI additionally uses
  `rag_llm_model` for the RAG engine). Environment variables override `.env`.
  **Policy:** `llm_provider` is a *preference, not a requirement* — it is tried
  first, then the remaining providers, skipping any without a key and any whose
  SDK fails to construct. An unknown `llm_provider` logs a warning and falls back
  to the default order rather than failing. Both `app/utils.py::get_tutor_agent`
  (LangChain) and `session.py::_configure_llama_defaults` (LlamaIndex) go through
  this module; **do not re-add a per-call-site if-chain.** `_configure_llama_defaults`
  deliberately logs rather than raises when no LLM is available, since indexing
  and retrieval still work without one.
- Gemini on the LlamaIndex side prefers `llama-index-llms-google-genai` and only
  falls back to the deprecated `llama-index-llms-gemini` (which wraps the retired
  `google.generativeai` SDK) if the former isn't installed.

Two embedding models are loaded in the same process (MiniLM for ranking,
bge-small for RAG) — that's intentional duplication for now, not a bug to
silently "fix" by merging, since they serve different scoring needs; only
consolidate this if you're deliberately redesigning ranking.

## 6. Development philosophy & conventions (keep following these)

- **Rationale-comment style.** Module and class docstrings explain *why*, not
  just what (see any file in `agent/`, `retrieval/embedder.py`, `config.py`).
  New non-trivial modules should keep this; don't strip it out during cleanup.
- **Pydantic as the contract layer.** `core/models.py` types flow through the
  entire system. Extend these models rather than inventing parallel dict
  shapes.
- **Protocol-based interfaces + constructor injection.** `SearchProvider` is a
  `typing.Protocol`; agents take a `BaseChatModel` and don't know which
  provider backs it; `PaperRanker` takes an injected `EmbeddingEngine`. Follow
  this pattern for new pluggable components instead of subclassing or feature
  flags.
- **`lru_cache` singletons** for expensive, stateless-enough services
  (`get_settings`, `get_db_manager`, `get_embedding_engine`,
  `get_paper_session_manager`, `get_search_agent`, `get_workspace_chat_store`
  in `app/utils.py`). The one thing that must **not** be a bare singleton is
  per-conversation chat memory — see `WorkspaceChatStore` and
  `PaperSession._build_chat_engine` for why memory is scoped by workspace_id
  and built fresh per call rather than cached on the session.
- **Logging**: module-level `logger = logging.getLogger(__name__)`, lazy `%s`
  formatting, info for lifecycle events, warning for recoverable failures
  (e.g. a search provider failing shouldn't crash the whole search).
- **`from __future__ import annotations`** everywhere for forward refs / `X | None` syntax on Python 3.11.
- **Shared helpers over duplication.** `agent/formatting.py` centralizes
  context-block formatting and JSON-markdown cleanup used by planner/tutor/critic;
  `WorkspaceManager._row_to_paper_metadata` centralizes the papers-row mapping;
  `session.py::_extract_source_nodes` centralizes citation-dict extraction for
  both single- and multi-paper chat. Reuse these rather than re-deriving the
  same logic in a new call site.

## 7. Resolved issues (kept for history — don't reintroduce these patterns)

The initial repository audit found a number of P0/P1 bugs; all have since
been fixed. Noted here so the same mistakes don't get reintroduced:

- `DocumentPipeline.retrieve()` used to call `index.as_query_engine().query()`
  just to fetch chunks (a full LLM synthesis call for pure retrieval). Now
  uses `index.as_retriever(...).retrieve(query)`. **Lesson:** use a retriever
  for retrieval, a query/chat engine only when you want generation.
- `TextChunk(metadata=meta)` used to pass raw LlamaIndex node metadata
  (which can contain ints) into a `dict[str, str]`-typed field, crashing on
  any paper with a `publication_year`. Now coerced to strings explicitly.
- `PaperSessionManager`'s cached `PaperSession` used to hold one persistent
  `condense_plus_context` chat engine per paper, so every workspace/user
  chatting about the same paper shared one conversation history. Fixed by
  building a fresh chat engine per call (`PaperSession._build_chat_engine`)
  seeded with caller-supplied history, with history now scoped per workspace
  in `app/utils.py::WorkspaceChatStore`. **Lesson:** a cached object that's
  safe to share for retrieval (the index) is not automatically safe to share
  for conversation state.
- Chat/retrieval used to only ever use `papers[0]` of a workspace. Fixed via
  `PaperSessionManager.chat_across_papers` + `MultiPaperRetriever`, which fans
  a query across every paper's index and merges by score.
- `WorkspaceManager._get_connection()` used to leak a SQLite connection on
  every call (the connection context manager only commits/rolls back, it
  doesn't close). Now a `@contextmanager` that always closes.
- CORS used `allow_origins=["*"]` with `allow_credentials=True` (spec-invalid).
  Fixed — credentials are off since the frontend doesn't use cookies/auth headers.
- `PDFDownloader` accepted any URL scheme (`file://` included) with no size
  cap. Now defaults to `http`/`https` only with a streamed byte cap; tests
  that need `file://` fixtures opt in explicitly via `allowed_schemes`.
- API handlers used to leak `str(e)` and print tracebacks to stdout. Now
  logged server-side via `logger.exception`, sanitized message to the client.
- `process_paper` used to write the paper into the workspace DB *before*
  indexing, so a failed index left a permanently unchattable paper in the
  workspace. Now indexes first, only persists to the DB on success.
- `sync_paper_metadata` used to reach into `WorkspaceManager._get_connection()`
  directly and duplicate the row-mapping logic. Now calls the public
  `WorkspaceManager.get_paper_by_id`.
- `s2FieldsOfStudy` entries (dicts in the real Semantic Scholar API) used to
  get `str()`-stringified wholesale into keywords. Now the `category` field
  is extracted specifically via `_normalize_field_of_study`.
- Frontend: `alert()` for errors, a `NodeJS.Timeout` type in browser code,
  dead-end workspace cards, and static do-nothing summary tabs are all fixed
  — see §8.
- Multi-provider LLM support was first written as two independent if-chains
  (one in `app/utils.py`, one in `session.py`) that hardcoded model ids, hardcoded
  a gemini→groq→openai precedence, and ignored the `llm_provider` setting.
  Consolidated into `paperpilot/llm/factory.py` (§5). **Lesson:** the same
  decision made in two places will drift; make it once and inject the result.
- `Settings.model_config` used `env_file=".env"`, which resolves against the
  process CWD — so running the API the documented way (from `src/`) silently
  ignored the repo-root `.env`, and keys present only there looked unset. Now
  anchored to the repo root via `Path(__file__).parents[2]`.
- `providers.py` called `socket.setdefaulttimeout(15.0)` at import time to stop
  python-arxiv from hanging. That default is process-global and also applied to
  the multi-minute Hugging Face model downloads in the same process. Now scoped
  to the arXiv fetch via the `_socket_timeout` contextmanager.
- `app/api.py` used the deprecated `@app.on_event("startup")`; now a `lifespan`
  async contextmanager.

### Found by live end-to-end testing (2026-07-21)

These were all invisible to the offline suite — every one needed a real call.

- **Summaries could never work.** `SummarizerService` retrieved using the
  *prompt* ("Summarize this paper in five clear sentences"). An instruction
  resembles no passage in a paper, so every chunk scored below
  `rag_similarity_threshold` and all ten levels refused with "I cannot find the
  answer in the provided text." Fixed by retrieving on the paper's own
  title + abstract with the cutoff disabled (`apply_similarity_cutoff=False`,
  `rag_summary_top_k`). **Lesson:** embedding retrieval matches text that
  *looks like* the target passage; an instruction is not such a text.
- **Every citation rendered "Page N/A".** `PyMuPDFReader` stores the page in
  `metadata["source"]`, not `page_label`. Centralized in
  `session.py::extract_page_number`, which only trusts `source` when it is
  numeric (other loaders put a filename there).
- **A dead API key took the whole app down.** Provider *construction* succeeds
  with an exhausted-quota key; only the call 429s. `build_chat_model` now wires
  the remaining providers via LangChain `with_fallbacks`, and every provider is
  built with `max_retries=0` so a hard quota error switches providers
  immediately instead of retrying a known-dead one. **Lesson:** "the client
  constructed" is not "the provider works".
- **Gemini hung forever behind an intercepting proxy.** `langchain-google-genai`
  defaults to gRPC, whose TLS is done in C against its own root store — it
  ignores both `certifi` and `truststore`, and retries handshake failures
  indefinitely rather than erroring. Pinned to `transport="rest"`.
- **TLS failed for everything** (arXiv, S2, Hugging Face, all LLM providers)
  with `CERTIFICATE_VERIFY_FAILED` on a machine with TLS interception. Fixed by
  `paperpilot/net.py`. **Never "fix" this with `verify=False`** — the app sends
  API keys in request headers.
- **A throttled critic threw away a good answer.** The audit is the second
  full-context call and so the most likely to hit a token limit; a failure there
  used to propagate and lose an answer the tutor had already produced. Now
  caught: the answer is returned unaudited with `approved=False` and a critique
  saying the audit did not run.
- Semantic Scholar 429s the first request of a session even when correctly
  paced at its 1 rps grant, so `semantic_scholar_max_retries` was raised from
  2 to 3 — with 2 the retry budget ran out and an entire search returned no S2
  results at all.

## 8. Feature status vs. the vision (`ProjectIdea.txt`)

| Area | Status |
|---|---|
| Paper discovery + weighted ranking | Done, well-tested |
| PDF download + validation | Done, hardened (scheme allowlist + size cap) |
| Single-paper RAG chat | Working end-to-end (Stack B) |
| Multi-paper workspace chat | Working — `chat_across_papers` fans out across every paper's index and merges by score |
| Tutor / Critic / self-correction loop | **Live in production** via `GroundedQAService` on `/api/workspaces/{id}/chat` (§4). Answers carry citations and an audit verdict; the UI labels flagged and refused answers |
| Planner agent / LangGraph pipeline | Implemented and tested, still not invoked by any endpoint — the remaining inert piece (§11) |
| Metadata sync from arXiv/Semantic Scholar | Implemented (`pipeline.py::sync_paper_metadata`) |
| Multi-level summarization | Done — `SummarizerService` owns all 10 levels from the vision doc, generates them through the grounded path, and caches per paper+level on disk. Tabs are driven by `GET /api/summary-levels`, with an explicit Regenerate action. |
| Multi-paper comparison, learning roadmaps, quizzes, long-term memory | Not started |
| Structured citations | Done — every chat answer returns citations (page, filename, score, excerpt); `AnswerMessage.tsx` renders them collapsibly in both chat surfaces |
| Streaming responses | `PaperSession.stream()` exists but no endpoint exposes it |
| Workspace browsing UI | `WorkspaceDetail` page (`/workspace/:workspaceId`) lists papers and lets you chat with the whole workspace; `ResearchLibrary` cards now navigate there |
| Live agent-activity status | Navbar reflects real in-flight requests via `AgentActivityContext`, not a hardcoded string |

## 9. Working agreement for making changes here

- Understand the current implementation before touching it; prefer extending
  existing modules (`core/models.py`, `services/paper_chat/`,
  `workspace/manager.py`, `search/`) over parallel implementations.
- LlamaIndex is the permanent RAG layer (§4) — new document-intelligence work
  goes through `PaperSession`/`PaperSessionManager`, not a new pipeline.
- Bug fixes, refactors, dead-code removal, typing/logging/test/doc
  improvements, and other changes that don't alter the architecture or vision
  can be made proactively without asking first.
- Architecture changes, deleting a major subsystem (e.g. removing Stack A
  entirely), swapping frameworks, breaking API changes, or DB strategy changes
  need a check-in first.
- Keep the frontend's current design language, component structure, and
  Tailwind token system; improve functionality and wiring, don't redesign.

## 10. Testing expectations

- `pytest tests/ -v` (from repo root; `pyproject.toml` sets `pythonpath = ["src"]`).
- Tests must stay offline: mock HTTP (`httpx`/`urllib`), use
  `tests/test_tutor.py::StubChatModel` (or extend it, as
  `test_graph_integration.py::GraphStubLLM` does) instead of calling a real
  LLM, use `tmp_path` for filesystem-touching tests.
- Never delete a failing test to make the suite green — fix the code or the
  test.
- New endpoints/features need at least one offline test following the
  existing per-module test file convention (`tests/test_<module>.py`).
- Current offline suite: 115 tests pass fully offline. `tests/test_api.py` uses
  FastAPI `dependency_overrides` + `TestClient` (deliberately *not* as a context
  manager, so the model-warming lifespan is skipped) — follow that pattern for
  new endpoints.
- Don't run two pytest processes at once against this repo; they contend on the
  model/index caches and a 20s suite balloons to minutes. `tests/test_embedder.py`
  (9 tests) downloads `all-MiniLM-L6-v2` from Hugging Face on first run and
  needs network access — expect it to fail with an SSL/connection error in
  network-restricted sandboxes; that's an environment limitation, not a
  regression.
- Frontend: `npx tsc -b` (type-check) and `npm run build` (production build)
  in `frontend/` should both be clean before considering a frontend change done.

## 11. Roadmap (recommended order)

1. Security/ops follow-ups: background indexing for slow PDF processing
   (still synchronous in the request, and now slower since chat does up to
   3 LLM round-trips), rate limiting, auth if this ever leaves localhost.
2. Wire the Planner agent in: decompose a user goal into subtasks and drive
   search + retrieval from it. This is the last inert part of Stack A.
3. Remaining vision features: multi-paper comparison (a Comparison agent over
   `retrieve_across_papers`), learning roadmaps, quizzes, and persistent
   long-term memory (`WorkspaceChatStore` is still process-local).
4. Expose streaming (`PaperSession.stream()`) so long grounded answers render
   progressively — currently a critic retry means a long silent wait.

## 12. Git workflow

- Small, focused commits; imperative present-tense messages consistent with
  existing history style.
- Never commit `data/` or `storage/` (both gitignored).
- Don't force-push or rewrite shared history without explicit confirmation.
