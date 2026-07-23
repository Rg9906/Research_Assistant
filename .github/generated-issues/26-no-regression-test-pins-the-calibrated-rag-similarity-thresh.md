---
title: "No regression test pins the calibrated `rag_similarity_threshold=0.60` value"
labels: ['tests', 'backend']
difficulty: Medium
estimate: "2 hours"
category: "🧪 Testing"
---

# No regression test pins the calibrated `rag_similarity_threshold=0.60` value

**Category:** 🧪 Testing

## Background

CLAUDE.md §7 documents, in detail, that `rag_similarity_threshold` was moved from 0.7 to 0.60 based on *measured* cosine-similarity bands on a real paper with `bge-small-en-v1.5` (relevant questions: 0.65-0.77, off-topic: 0.48-0.57). This is genuinely valuable, hard-won calibration data — but nothing in the test suite encodes it, so a future change to `rag_embedding_model` (or an unrelated refactor that quietly resets the default) has no test surface to fail against.

## Why it matters

Undocumented, uncovered calibration constants are exactly the kind of "institutional knowledge" that silently rots the moment the person who measured it stops being the one reviewing every PR — which is the whole point of preparing this project for outside contributors.

## Proposed solution

Add a test (can be a simple config-level assertion, or ideally a small fixture reproducing the measured score bands with a stubbed embedding model) that fails loudly if `rag_similarity_threshold` or `rag_embedding_model` change without an accompanying, deliberate re-calibration.

## Acceptance Criteria

- [ ] A test fails if `rag_similarity_threshold` or `rag_embedding_model`'s default changes without an explicit update to the test (i.e. the test forces a conscious decision, not a silent drift)
- [ ] The test or its docstring links back to CLAUDE.md §7 for the reasoning

## Suggested files

`tests/test_paper_chat.py` or a new `tests/test_config_calibration.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

tests, backend

## Dependencies

None
