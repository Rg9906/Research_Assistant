---
title: "No test exercises `GroundedQAService.answer` with `apply_similarity_cutoff=False` returning zero chunks"
labels: ['good first issue', 'tests', 'backend']
difficulty: Easy
estimate: "1 hour"
category: "🧪 Testing"
---

# No test exercises `GroundedQAService.answer` with `apply_similarity_cutoff=False` returning zero chunks

**Category:** 🧪 Testing

## Background

`SummarizerService.summarize` calls `qa_service.answer(..., apply_similarity_cutoff=False)`. The retrieval still runs `MultiPaperRetriever` first — if a paper's index is empty or the retriever genuinely returns nothing (e.g. a degenerate one-page PDF), `nodes_to_chunks` produces an empty list even with the cutoff disabled, and `GroundedQAService.answer` refuses. It's not clear from `tests/test_grounded_qa.py` or `tests/test_summarizer.py` that this specific edge case (cutoff disabled, retrieval still empty) is covered.

## Why it matters

This is the one place summarization could fail in a confusing way (a summary silently refusing for a real, valid, if very short, paper) without a clear signal of why.

## Proposed solution

Add a test that stubs retrieval to return zero nodes with `apply_postprocessors=False` and asserts `SummarizerService.summarize` returns the tutor's refusal text with `from_cache=False` rather than raising or crashing.

## Acceptance Criteria

- [ ] A test covers zero-node retrieval with the similarity cutoff disabled
- [ ] The test asserts a clean refusal response rather than an exception

## Suggested files

`tests/test_grounded_qa.py` or `tests/test_summarizer.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, tests, backend

## Dependencies

None
