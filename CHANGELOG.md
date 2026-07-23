# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **PDF availability as a ranking dimension.** Search results are now scored on
  how likely their PDF can actually be downloaded and indexed (open repository >
  direct `.pdf` > publisher landing page > none), so chattable papers rank above
  abstract-only ones. Configurable via `search_weight_availability`.
- **arXiv PDF recovery.** A Semantic Scholar record that only exposes a publisher
  landing page but carries an arXiv id is rewritten to the canonical
  `arxiv.org/pdf/...` link before ranking and before the API response, turning
  many previously un-chattable results into openable ones.
- **"Chat Ready" / "No PDF" badges** on discovery cards to distinguish papers
  that can be chatted with from abstract-only ones.
- Open-source project scaffolding: `LICENSE`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, `ROADMAP.md`, this changelog, GitHub issue
  and pull-request templates, funding metadata, and CI workflows for tests and
  linting.
- `ruff` configuration and dev dependency for Python linting.

### Fixed

- Removed unused imports across the package and tests, an undefined `Any`
  annotation in `graph/builder.py`, a dead local in `graph/nodes.py`, and a
  `not in` membership style issue in `agent/critic.py`, so the lint baseline is
  clean.

## [0.1.0] — Initial baseline

The first working end-to-end version of PaperPilot AI.

### Added

- **Paper discovery** across arXiv and Semantic Scholar, with de-duplication
  (DOI → arXiv id → Jaccard title similarity) and weighted ranking (semantic
  similarity + citation impact + recency).
- **Document intelligence (RAG)** — PDF download and validation, PyMuPDF parsing,
  chunking, embedding (`BAAI/bge-small-en-v1.5`), and per-paper LlamaIndex
  persistence with a content-hash fingerprint cache.
- **Single- and multi-paper grounded chat** — fanned out across every paper in a
  workspace and merged by score, with structured citations.
- **Tutor / Critic self-correction loop** via `GroundedQAService` — answers are
  generated strictly from retrieved context and independently audited.
- **Multi-level summarization** — ten summary views cached per paper and level.
- **LangGraph multi-agent pipeline** (Planner → Search → Tutor → Critic), built
  and tested (not yet wired into the API).
- **Multi-provider LLM support** (OpenAI, Gemini, Groq) via a single selection
  policy in `paperpilot/llm/factory.py`, with automatic fallback.
- **FastAPI backend** and a **React 19 + Vite + TypeScript + Tailwind** frontend
  (discovery, library, paper detail with tabbed AI views + chat, workspace chat).
- **SQLite-backed workspace persistence** and process-local per-workspace chat
  memory.
- Hardening for TLS interception, Hugging Face offline caching, and quota-limited
  API pacing (see CLAUDE.md §7).

[Unreleased]: https://github.com/Rg9906/Research_Assistant/compare/main...HEAD
