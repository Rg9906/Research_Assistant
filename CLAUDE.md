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
| `src/paperpilot/config.py` | `Settings` (pydantic-settings), `.env`-backed, `get_settings()` cached singleton. |
| `src/paperpilot/document/downloader.py` | `PDFDownloader` — fetch, validate (magic bytes + PyMuPDF open), retry with backoff, scheme allowlist (http/https by default), and a streamed size cap. |
| `src/paperpilot/retrieval/embedder.py` | `EmbeddingEngine` wrapping `sentence-transformers` (MiniLM). Used only by the ranker (see §4). |
| `src/paperpilot/search/` | `providers.py` (arXiv, Semantic Scholar via a `SearchProvider` Protocol), `ranker.py` (weighted scoring), `agent.py` (`SearchAgent`: fetch → dedupe → rank). Solid, well-tested. |
| `src/paperpilot/agent/` | `planner.py`, `tutor.py`, `critic.py` — LangChain `BaseChatModel`-based agents implementing the grounded-QA + self-critique contract, plus `formatting.py` (shared `clean_json_markdown` / `format_chunks_as_context` helpers used by all three). See §4 for their current (disconnected) status. |
| `src/paperpilot/graph/` | `state.py` (`AgentState` TypedDict), `nodes.py` (`AgentNodes`), `builder.py` (LangGraph `StateGraph` + routers). Compiles a planner→search→retrieve→tutor→critic loop. Not wired to the API — see §4. |
| `src/paperpilot/services/paper_chat/` | **The live RAG stack.** `session.py` (`PaperSession`, `PaperSessionManager`, `MultiPaperRetriever`) owns LlamaIndex document loading, chunking, indexing, persistence, single- and multi-paper chat. `exceptions.py` holds the domain exception hierarchy. |
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
  --> PaperSessionManager.chat_across_papers(papers, query, chat_history)
        --> 1 paper:  session.chat() directly
        --> N papers: MultiPaperRetriever fans the query out across every
                       paper's index, merges by score, feeds a fresh
                       CondensePlusContextChatEngine
  --> WorkspaceChatStore (app/utils.py) persists the returned chat_history,
      scoped per workspace_id — NOT baked into the shared PaperSession
```

## 4. The two-stack reality (read this before touching RAG code)

There are **two parallel implementations** of "answer a question about a paper."
Only one is live in the product.

- **Stack A — LangGraph multi-agent pipeline** (`agent/`, `graph/`, `retrieval/embedder.py`
  for ranking only). Implements the full vision: Planner decomposes the query,
  Search discovers papers, Tutor answers strictly from retrieved chunks with a
  refusal string, Critic audits grounding/relevance/style and can force up to 3
  retries. This is well-tested (`tests/test_planner.py`, `test_tutor.py`,
  `test_critic.py`, `test_graph_flow.py`, `test_graph_integration.py`) but
  **no FastAPI endpoint invokes `compile_agent_graph`**. It is inert.

- **Stack B — LlamaIndex session stack** (`services/paper_chat/session.py`,
  used via `app/api.py`). This is what actually answers user chat requests
  today, including multi-paper workspace chat (`chat_across_papers`,
  `MultiPaperRetriever`). It applies a similarity-cutoff postprocessor
  (`rag_similarity_threshold`, default 0.7) plus an optional reranker before
  generation, but has no explicit grounding/refusal prompt and no critic —
  the LlamaIndex default chat prompts, not the Tutor/Critic contract.

**Working agreement going forward:** LlamaIndex (Stack B) is the permanent
document-intelligence layer. Do not build a third RAG implementation. The
long-term direction is to make Stack A's Tutor/Critic agents *consume* Stack B's
`PaperSession`/`MultiPaperRetriever` for retrieval so the grounding/critique
contract actually reaches production, and to retire the now-unused parts of
Stack A gradually rather than deleting it outright.

## 5. Configuration (`src/paperpilot/config.py`)

`Settings` (pydantic-settings, `.env`-backed) — key groups:
- Paths: `data_dir`, `papers_dir`, `index_dir`, `db_path`, `storage_papers_dir`.
- Legacy chunking/ranking embedding: `embedding_model_name` (`all-MiniLM-L6-v2`) — used only by `PaperRanker` for title/abstract similarity scoring, not for paper chat.
- RAG (LlamaIndex, Stack B): `rag_chunk_size`/`rag_chunk_overlap` (512/50), `rag_top_k`, `rag_embedding_model` (`BAAI/bge-small-en-v1.5`), `rag_llm_model` (`gpt-4o-mini`), `rag_similarity_threshold` (0.7 — wired into every session's `node_postprocessors` as a `SimilarityPostprocessor`, applied before the optional reranker), `rag_rerank_enabled`/`rag_rerank_model`/`rag_rerank_top_n`.
- Search ranking weights: `search_weight_similarity/citations/recency` (auto-normalized to sum to 1 in `PaperRanker.__init__` if they don't), `search_decay_rate`.
- `llm_provider`/`llm_model_name`/`llm_temperature`/`openai_api_key` feed both the LangGraph chat model (`app/utils.py::get_tutor_agent`) and, via `os.environ`, LlamaIndex's global `Settings.llm` (`session.py::_configure_llama_defaults`).

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

## 8. Feature status vs. the vision (`ProjectIdea.txt`)

| Area | Status |
|---|---|
| Paper discovery + weighted ranking | Done, well-tested |
| PDF download + validation | Done, hardened (scheme allowlist + size cap) |
| Single-paper RAG chat | Working end-to-end (Stack B) |
| Multi-paper workspace chat | Working — `chat_across_papers` fans out across every paper's index and merges by score |
| Planner / Tutor / Critic / self-correction loop | Implemented and tested, still not connected to the API (§4) — the biggest remaining gap between vision and product |
| Metadata sync from arXiv/Semantic Scholar | Implemented (`pipeline.py::sync_paper_metadata`) |
| Multi-level summarization (quick/beginner/technical/contribution/limitations) | Frontend tabs are functional: "Quick" shows the abstract, the other four call `chat_across_papers` with a tailored prompt on demand once the paper has been processed. No dedicated summarization *service* yet — this reuses the general chat path, not a purpose-built multi-level summarizer with caching/regeneration. |
| Multi-paper comparison, learning roadmaps, quizzes, long-term memory | Not started |
| Streaming responses / structured citations | `PaperSession.stream()` and `get_sources()` exist but no endpoint exposes them |
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
- Current offline suite: 61 tests pass fully offline. `tests/test_embedder.py`
  (9 tests) downloads `all-MiniLM-L6-v2` from Hugging Face on first run and
  needs network access — expect it to fail with an SSL/connection error in
  network-restricted sandboxes; that's an environment limitation, not a
  regression.
- Frontend: `npx tsc -b` (type-check) and `npm run build` (production build)
  in `frontend/` should both be clean before considering a frontend change done.

## 11. Roadmap (recommended order)

1. Decide and implement how Stack A's grounding/critique contract reaches
   production traffic (most likely: Tutor/Critic wrap `PaperSession`/
   `MultiPaperRetriever` retrieval instead of the LlamaIndex default chat
   prompts). This is the largest remaining gap between the vision doc and
   the shipped product.
2. Security/ops follow-ups: background indexing for slow PDF processing
   (currently synchronous in the request), rate limiting, auth if this ever
   leaves localhost.
3. Purpose-built summarization service: cache generated summaries per
   paper/tab instead of re-querying chat on every click; extend to the
   remaining vision features (multi-paper comparison, learning roadmaps,
   quizzes, persistent long-term memory).
4. Expose streaming (`PaperSession.stream()`) and structured citations
   (`get_sources()`) through the API for a more responsive, verifiable chat UI.

## 12. Git workflow

- Small, focused commits; imperative present-tense messages consistent with
  existing history style.
- Never commit `data/` or `storage/` (both gitignored).
- Don't force-push or rewrite shared history without explicit confirmation.
