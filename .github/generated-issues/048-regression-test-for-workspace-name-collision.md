# Add a regression test for the workspace-name collision fix

## Background

Issue #002 fixes auto-created single-paper workspace names colliding between
two different papers with similar titles. Like any bug fix, it needs a
regression test that fails on the old code and passes on the new code —
otherwise the collision can silently come back in a future refactor of
workspace-creation logic.

## Why it matters

This class of bug (two different papers ending up in the same
auto-generated workspace) is exactly the kind of thing that's invisible in
manual testing (you'd need two specific title collisions to notice) and easy
to reintroduce silently.

## Proposed solution

Once #002 lands, add a test in `tests/test_workspace.py` or
`tests/test_api.py` that processes two papers whose titles collide under the
old truncation logic and asserts they land in two distinct workspaces with
distinct names/IDs.

## Acceptance criteria

- [ ] Test fails against the pre-#002 behavior (verify by temporarily
      reverting the fix locally) and passes after it
- [ ] Test uses realistic title strings that actually trigger the collision

## Suggested files

- `tests/test_workspace.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

tests, backend

## Dependencies

Depends on #002 landing first.
