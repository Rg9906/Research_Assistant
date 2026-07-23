---
title: "No Docker/devcontainer setup — native install requires PyTorch, FAISS, and LlamaIndex build tooling"
labels: ['documentation', 'backend', 'enhancement']
difficulty: Medium
estimate: "1 day"
category: "📚 Documentation"
---

# No Docker/devcontainer setup — native install requires PyTorch, FAISS, and LlamaIndex build tooling

**Category:** 📚 Documentation

## Background

README.md's Quick Start step 2 (`pip install -e ".[dev]"`) pulls in PyTorch, sentence-transformers, faiss-cpu, LlamaIndex, and LangGraph natively — "it will take a few minutes" per the README's own warning, and on some platforms (older CPUs without AVX2, some ARM setups) these packages have real installation friction (wheel availability, build tooling). There's no containerized alternative.

## Why it matters

Lowering the setup-friction floor is one of the highest-leverage things a maintainer can do for contributor retention — a contributor who hits a confusing native build failure on their very first setup step often just leaves instead of debugging it.

## Proposed solution

Add a `Dockerfile` (and optionally a `.devcontainer/devcontainer.json` for one-click VS Code / GitHub Codespaces setup) that installs backend dependencies in a known-good base image, mounts the repo, and runs `uvicorn` from `src/`. Document it as an alternative path in README.md's Quick Start, not a replacement for the native instructions.

## Acceptance Criteria

- [ ] A working `Dockerfile` builds the backend and runs the test suite inside the container
- [ ] README.md documents the Docker path as an alternative Quick Start route
- [ ] (Optional but recommended) a `.devcontainer/devcontainer.json` enables one-click Codespaces/VS Code setup

## Suggested files

New `Dockerfile`, new `.devcontainer/devcontainer.json`, `README.md`

## Difficulty

Medium

## Estimated time

1 day

## Labels

documentation, backend, enhancement

## Dependencies

None
