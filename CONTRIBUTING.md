# Contributing to PaperPilot AI

First off — thank you for taking the time to contribute! PaperPilot AI is an
autonomous multi-agent research assistant, and it gets better with every issue,
idea, and pull request.

This guide covers how to get set up, the conventions we follow, and what to
expect from the review process. For a deep understanding of *how the code
actually works* — the architecture, the two RAG stacks, and the reasoning
behind non-obvious decisions — read **[CLAUDE.md](./CLAUDE.md)**. It is the
engineering source of truth and is kept in sync with the code.

## Table of contents

- [Code of Conduct](#code-of-conduct)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Project layout](#project-layout)
- [Running tests and linters](#running-tests-and-linters)
- [Coding conventions](#coding-conventions)
- [Commit and pull request guidelines](#commit-and-pull-request-guidelines)
- [Reporting bugs and requesting features](#reporting-bugs-and-requesting-features)

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to
uphold it. Please report unacceptable behaviour to the maintainer.

## Ways to contribute

You don't have to write code to help:

- **Report a bug** — open an issue using the *Bug report* template.
- **Request a feature** — open an issue using the *Feature request* template,
  and check [ROADMAP.md](./ROADMAP.md) first to see if it's already planned.
- **Improve documentation** — the *Documentation* issue template exists for
  exactly this. README, CLAUDE.md, and inline docstrings all count.
- **Pick up an issue** — issues labelled `good first issue` and `help wanted`
  are the best places to start.
- **Send a pull request** — see the guidelines below.

## Development setup

PaperPilot AI has a Python backend (`src/`) and a React frontend (`frontend/`).

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for the frontend)
- **Git**

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/Research_Assistant.git
cd Research_Assistant
```

### 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
```

This installs PyTorch, sentence-transformers, FAISS, LlamaIndex, and LangGraph
along with the dev tooling (`pytest`, `ruff`) — it can take a few minutes.

### 3. Configure environment

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS/Linux
```

At minimum, set `OPENAI_API_KEY` (or a Gemini/Groq key — see CLAUDE.md §5) to
enable chat and summarization. `SEMANTIC_SCHOLAR_API_KEY` is optional and raises
the free-tier search rate limit. **Never commit your `.env` or any API keys.**

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Run the backend

```bash
cd src
uvicorn app.api:app --reload --port 8000
```

`src/app` is not an installed package (it has no `__init__.py`), so it must be
run with `src/` as the working directory.

## Project layout

A quick map — see [README.md](./README.md#code-layout) and CLAUDE.md §2 for the
full breakdown.

```
src/paperpilot/    Installable package: search, ranking, RAG, agents, workspace
src/app/           FastAPI backend (not a package — run from src/)
frontend/          React 19 + Vite + TypeScript + Tailwind
tests/             pytest suite (offline-first, pythonpath=src)
```

## Running tests and linters

Everything below must pass before a pull request is ready for review. CI runs
the same checks (see `.github/workflows/`).

### Python tests

```bash
pytest tests/ -v
```

- The suite is **offline-first**: all external HTTP and LLM calls are mocked or
  stubbed. New tests must stay offline too — use `tests/test_tutor.py::StubChatModel`
  instead of a real LLM, `tmp_path` for filesystem tests, and mock `httpx`/`urllib`.
- `tests/test_embedder.py` downloads a model from Hugging Face on first run and
  needs network access; it is expected to fail in fully sandboxed environments
  and is skipped in CI.
- **Never delete a failing test to make the suite green** — fix the code or the
  test.
- Every new endpoint or feature needs at least one offline test following the
  `tests/test_<module>.py` convention.

### Python lint

```bash
ruff check src/ tests/
```

### Frontend

```bash
cd frontend
npx tsc -b        # type-check
npm run lint      # oxlint
npm run build     # production build
```

Both the type-check and the build should be clean before a frontend change is
considered done.

## Coding conventions

These mirror the conventions the codebase already follows (CLAUDE.md §6):

- **Explain *why*, not just *what*.** Module and class docstrings should capture
  the reasoning behind non-obvious decisions. Don't strip existing rationale
  comments during cleanup.
- **Pydantic is the contract layer.** Extend the models in
  `src/paperpilot/core/models.py` rather than inventing parallel dict shapes.
- **Protocol-based interfaces + constructor injection.** Follow the existing
  `SearchProvider` Protocol / injected-dependency pattern for new pluggable
  components instead of subclassing or feature flags.
- **`from __future__ import annotations`** at the top of every module.
- **Logging, not printing.** Use a module-level
  `logger = logging.getLogger(__name__)` with lazy `%s` formatting.
- **Prefer extending existing modules** over parallel implementations.
  LlamaIndex is the permanent RAG layer — new document-intelligence work goes
  through `PaperSession`/`PaperSessionManager`, not a new pipeline.
- **Match the surrounding code** in naming, comment density, and idiom.

Architecture-level changes (removing a subsystem, swapping a framework, breaking
API changes, DB strategy changes) should be discussed in an issue **before** you
open a pull request. Bug fixes, refactors, dead-code removal, typing/logging/test/doc
improvements are welcome without a prior discussion.

## Commit and pull request guidelines

- **Branch** off `main`: `git checkout -b fix/short-description`.
- **Keep commits small and focused**, with imperative present-tense messages
  ("Add availability weight to ranker", not "Added" or "Adds").
- **Never commit** `data/`, `storage/`, `.env`, `node_modules/`, or any secret.
- **Fill in the pull request template** — describe *what* changed and *why*,
  link the issue it closes, and confirm tests and linters pass.
- **One logical change per pull request** where possible; it makes review faster
  and history cleaner.
- Add a line to the `[Unreleased]` section of [CHANGELOG.md](./CHANGELOG.md) for
  any user-facing change.

A maintainer will review your pull request, may request changes, and will merge
it once it's ready. Please be patient and responsive to review comments — and
don't be discouraged by requests for changes; they're a normal part of the
process.

## Reporting bugs and requesting features

Use the [issue templates](https://github.com/Rg9906/Research_Assistant/issues/new/choose).
For security vulnerabilities, **do not open a public issue** — follow the process
in [SECURITY.md](./SECURITY.md) instead.

Thanks again for contributing. 🚀
