---
title: "Document (or eliminate) the loaded-twice embedding model footprint"
labels: ['good first issue', 'documentation', 'backend']
difficulty: Easy
estimate: "2 hours"
category: "🏗 Refactor"
---

# Document (or eliminate) the loaded-twice embedding model footprint

**Category:** 🏗 Refactor

## Background

CLAUDE.md §5 explicitly says loading both `all-MiniLM-L6-v2` (ranking, via `EmbeddingEngine`) and `BAAI/bge-small-en-v1.5` (RAG, via LlamaIndex's `HuggingFaceEmbedding`) in the same process is "intentional duplication for now, not a bug to silently fix by merging." That's a reasonable call, but there's no issue tracking *measuring* the actual memory/startup-time cost of this on a constrained host (e.g. a small VPS or a free-tier container), which matters a lot for anyone trying to self-host this project cheaply.

## Why it matters

Self-hosting cost/footprint is a real factor in whether contributors and users actually run this project themselves rather than just reading the code. A documented number ("~X00MB extra RSS, ~Ys extra cold-start") turns a vague tradeoff into an informed one.

## Proposed solution

Measure and document (in CLAUDE.md §5 and/or a new `docs/deployment.md`) the approximate memory and startup cost of running both embedding models, and note the minimum viable host spec for a small-scale deployment.

## Acceptance Criteria

- [ ] CLAUDE.md §5 (or a new deployment doc) states measured memory/startup overhead for running both models
- [ ] A recommended minimum host spec is documented for self-hosters
- [ ] No code changes required unless measurement reveals a problem worth fixing separately

## Suggested files

`CLAUDE.md`, new `docs/deployment.md` (optional)

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, documentation, backend

## Dependencies

None
