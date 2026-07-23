---
title: "Extract the repeated try/except → `_fail()` boilerplate in `app/api.py` into a shared decorator"
labels: ['good first issue', 'refactor', 'backend']
difficulty: Medium
estimate: "2 hours"
category: "🏗 Refactor"
---

# Extract the repeated try/except → `_fail()` boilerplate in `app/api.py` into a shared decorator

**Category:** 🏗 Refactor

## Background

Nearly every endpoint in `src/app/api.py` (`search_papers`, `chat_with_workspace`, `summarize_paper`, `process_paper`) repeats the same shape: `try: ... except SpecificException as e: raise _fail(502, ..., e) except Exception as e: raise _fail(500, ..., e)`. It's already been centralized once (the `_fail` helper itself), but the outer try/except structure is still duplicated four times with only the log message and status codes changing.

## Why it matters

This is a good, low-risk refactor for a new contributor to practice on: it touches a well-understood, well-tested file and reduces real duplication without changing any behavior.

## Proposed solution

Add a small decorator or dependency (e.g. `@handle_domain_errors(domain_exc=PaperChatException, log_prefix=...)`) that wraps a route function, catching the known domain exception with a 502 and anything else with a sanitized 500, exactly matching `_fail`'s current contract.

## Acceptance Criteria

- [ ] A shared decorator/helper replaces the four repeated try/except blocks in `app/api.py`
- [ ] Response bodies and status codes for every existing error case are byte-for-byte unchanged
- [ ] All of `tests/test_api.py` passes without modification

## Suggested files

`src/app/api.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

good first issue, refactor, backend

## Dependencies

None
