---
title: "No test covers `PaperSessionManager` session-cache reuse or concurrent access for the same paper"
labels: ['good first issue', 'tests', 'backend']
difficulty: Easy
estimate: "1.5 hours"
category: "🧪 Testing"
---

# No test covers `PaperSessionManager` session-cache reuse or concurrent access for the same paper

**Category:** 🧪 Testing

## Background

`get_or_create_session` (`src/paperpilot/services/paper_chat/session.py`) has an early-return cache-hit path (`if paper_id_str in self._active_sessions: return self._active_sessions[paper_id_str]`) that's central to the whole "don't rebuild the index every request" design, but there's no test in `tests/test_paper_chat.py` that calls `get_or_create_session` twice for the same paper and asserts the second call returns the exact same `PaperSession` object without re-downloading or re-parsing the PDF.

## Why it matters

This is the specific behavior issue #4 (LRU eviction) will need to modify — having a regression test in place *before* that change makes the refactor much safer to review and land.

## Proposed solution

Add a test that calls `get_or_create_session` twice with a mocked/stubbed downloader and index builder, asserting the second call is a cache hit (same object identity, downloader/parser not invoked again).

## Acceptance Criteria

- [ ] A test asserts calling `get_or_create_session` twice for the same paper returns the same `PaperSession` instance
- [ ] The test asserts the PDF downloader is only invoked once across both calls
- [ ] Test stays fully offline

## Suggested files

`tests/test_paper_chat.py`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

good first issue, tests, backend

## Dependencies

None
