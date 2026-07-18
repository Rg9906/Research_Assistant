# 🚀 PaperPilot AI

> An autonomous research assistant that discovers academic papers, ranks them, indexes them, and lets you chat with them — grounded in the actual paper text, not vibes.

PaperPilot AI searches arXiv and Semantic Scholar, ranks results with a weighted scoring model (semantic similarity + citation impact + recency), downloads and indexes selected papers with LlamaIndex, and answers questions about them through a chat interface.

For the full architecture, current technical debt, and engineering conventions, see **[CLAUDE.md](./CLAUDE.md)** — it's the source of truth for how this repository actually works today, kept in sync with the code rather than aspirational.

---

## Architecture at a glance

```
frontend/          React 19 + Vite + TypeScript + Tailwind — search UI, workspace library, paper chat
src/app/           FastAPI backend (api.py, utils.py) — the HTTP layer the frontend talks to
src/paperpilot/    Installable Python package — search, ranking, document download,
                    LlamaIndex-backed paper chat, SQLite workspace persistence
```

There is also a LangGraph multi-agent pipeline (`src/paperpilot/agent/`, `src/paperpilot/graph/`) implementing a Planner → Search → Tutor → Critic self-correction loop. It's fully built and tested but **not currently wired into the API** — see CLAUDE.md §4 for why and what's planned.

### Search & Ranking
Queries arXiv and Semantic Scholar in parallel, merges duplicate results (DOI → arXiv ID → Jaccard title similarity), and ranks the merged set with:
- **Semantic similarity** — cosine similarity between the query and each paper's title+abstract embedding
- **Citation impact** — log-normalized citation count
- **Recency** — exponential age decay

### Document Intelligence (RAG)
Selected papers are downloaded, parsed with PyMuPDF, chunked, embedded (`BAAI/bge-small-en-v1.5`), and indexed with LlamaIndex (`VectorStoreIndex`), persisted per-paper under `storage/papers/paper_<id>/` with a content-hash fingerprint so re-processing an unchanged PDF just loads the cached index. Chat is grounded via a `condense_plus_context` chat engine; multi-paper workspaces fan a query out across every paper's index and merge results by score.

---

## Quick Start

### 1. Clone & set up a virtual environment
```bash
git clone https://github.com/Rg9906/Research_Assistant.git
cd Research_Assistant

python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies
```bash
pip install -e ".[dev]"
```
This installs PyTorch, sentence-transformers, FAISS, LlamaIndex, and LangGraph — it will take a few minutes.

### 3. Configure environment
```bash
copy .env.example .env    # Windows
cp .env.example .env      # macOS/Linux
```
At minimum, set `OPENAI_API_KEY` in `.env` to enable chat/summarization. `SEMANTIC_SCHOLAR_API_KEY` is optional (raises the free-tier rate limit).

### 4. Run the test suite
```bash
pytest tests/ -v
```
61 tests run fully offline (all external calls mocked/stubbed). A further 9 tests in `tests/test_embedder.py` download the `all-MiniLM-L6-v2` model from Hugging Face on first run and require network access — they're skipped automatically in network-restricted environments.

### 5. Run the backend
```bash
cd src
uvicorn app.api:app --reload --port 8000
```
`src/app` isn't an installed package (no `__init__.py`), so it must be run with `src/` as the working directory / on `sys.path`.

### 6. Run the frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Code Layout

```
src/paperpilot/
├── core/                 # Pydantic data models: PaperMetadata, TextChunk, RetrievalResult, ...
├── config.py             # Pydantic Settings — .env-backed configuration
├── document/             # PDF downloader (validation, retries, scheme/size safety checks)
├── retrieval/             # Sentence-transformers embedder (used by the ranker)
├── search/               # arXiv + Semantic Scholar providers, dedup/merge, weighted ranker
├── services/paper_chat/  # PaperSession / PaperSessionManager — the live LlamaIndex RAG stack
├── workspace/            # SQLite-backed WorkspaceManager (workspaces, papers, mappings)
├── pipeline.py           # Facade connecting workspace + paper_chat for the LangGraph path
├── agent/                # Planner / Tutor / Critic LangChain agents (LangGraph path)
└── graph/                # LangGraph StateGraph wiring the agents together

src/app/                  # FastAPI backend consumed by the frontend
frontend/                 # React + Vite + TypeScript UI
tests/                    # pytest suite (offline-first, pythonpath=src)
```

---

## Roadmap

See CLAUDE.md §11 for the actively-maintained roadmap. In short: stabilize the current RAG path, decide how the Planner/Tutor/Critic grounding loop reaches production traffic, then build out comparison/summarization/roadmap-generation features on a solid foundation.

---

## License

MIT.
