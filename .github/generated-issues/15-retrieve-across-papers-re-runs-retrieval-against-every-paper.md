---
title: "`retrieve_across_papers` re-runs retrieval against every paper's index even for single-paper workspaces"
labels: ['backend', 'performance']
difficulty: Easy
estimate: "2 hours"
category: "⚡ Performance"
---

# `retrieve_across_papers` re-runs retrieval against every paper's index even for single-paper workspaces

**Category:** ⚡ Performance

## Background

`GroundedQAService.answer` always calls `session_manager.retrieve_across_papers(papers, ...)`, which builds a `MultiPaperRetriever` over every paper's independent `VectorStoreIndex` and merges by score — the general multi-paper path. For the very common case of a single-paper workspace (every paper auto-processed via `/api/papers/process` starts in its own one-paper workspace), this goes through the merge/sort machinery for a list of exactly one retriever with nothing to merge.

## Why it matters

Not a correctness issue, just unnecessary indirection on the single most common request shape in the product (every "chat about this one paper" interaction). `PaperSessionManager.chat_across_papers` already has this single-session fast path (`if len(sessions) == 1: ...`) — `retrieve_across_papers` doesn't.

## Proposed solution

Add the same single-session shortcut to `retrieve_across_papers`: when `len(sessions) == 1`, retrieve directly from that session's own retriever instead of constructing a `MultiPaperRetriever`.

## Acceptance Criteria

- [ ] A one-paper call to `retrieve_across_papers` skips `MultiPaperRetriever` entirely
- [ ] Multi-paper behavior is unchanged (existing tests in `tests/test_paper_chat.py`/`tests/test_grounded_qa.py` still pass)
- [ ] A new test confirms the single-session path returns identical results to the current multi-session code path for one paper

## Suggested files

`src/paperpilot/services/paper_chat/session.py`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

backend, performance

## Dependencies

None
