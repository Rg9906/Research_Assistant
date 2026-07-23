---
title: "`.env.example` is missing roughly 20 documented `Settings` fields"
labels: ['good first issue', 'documentation']
difficulty: Easy
estimate: "2 hours"
category: "📚 Documentation"
---

# `.env.example` is missing roughly 20 documented `Settings` fields

**Category:** 📚 Documentation

## Background

`config.py`'s `Settings` class defines and thoroughly documents (via inline comments) fields like `rag_top_k`, `rag_similarity_threshold`, `rag_lead_chunks`, `rag_chunk_size`/`rag_chunk_overlap`, `rag_rerank_enabled`/`rag_rerank_model`/`rag_rerank_top_n`, `rag_prefetch_enabled`/`rag_prefetch_workers`, `llm_temperature`, and all four `search_weight_*` ranking weights plus `search_decay_rate` — none of which appear in `.env.example`. A contributor who wants to tune retrieval or ranking behavior has to go read `config.py` source directly to even discover these knobs exist.

## Why it matters

`.env.example` is the first place any new contributor or self-hoster looks for "what can I configure," and right now it only covers LLM provider keys and a handful of RAG/search settings — most of the genuinely interesting, well-documented tuning knobs in this project are invisible there.

## Proposed solution

Add every currently-undocumented `Settings` field to `.env.example`, each commented out with its default value and a short one-line summary of what it does (the detailed rationale can stay in `config.py` and CLAUDE.md §5 — `.env.example` just needs enough to make each knob discoverable).

## Acceptance Criteria

- [ ] Every field in `Settings` (config.py) that a self-hoster might reasonably want to tune has a corresponding, commented-out entry in `.env.example`
- [ ] Each entry has at least a one-line description and its default value

## Suggested files

`.env.example`, `src/paperpilot/config.py`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, documentation

## Dependencies

None
