# Confirm before deleting a workspace

## Background

Issue #029 wires up the previously-unused `DELETE /api/workspaces/{id}`
endpoint in the UI. Deleting a workspace is destructive and irreversible
(it cascades to remove paper associations and chat history), so it should
not be a single, un-confirmed click.

## Why it matters

An accidental click on a delete affordance (easy to do on a card-based
grid layout, especially on mobile where tap targets are close together)
should not silently and irreversibly destroy a workspace's chat history
with no chance to undo. This is a small but important safety net that
should ship alongside — not after — #029.

## Proposed solution

Add a lightweight confirmation step before calling `deleteWorkspace` — an
inline "Are you sure? Confirm / Cancel" state on the card (avoiding a
native `window.confirm()`, which the project's own conventions steer away
from — CLAUDE.md §8 already lists replacing `alert()` for errors as a
resolved issue, and native dialogs are a similar UX smell) is preferable
to a full modal for something this contained.

## Acceptance criteria

- [ ] Deleting a workspace requires an explicit confirmation step, not a
      single click.
- [ ] The confirmation UI matches the existing design language (no native
      `window.confirm`/`alert`).
- [ ] Canceling leaves the workspace untouched.

## Suggested files

- `frontend/src/components/ResearchLibrary.tsx`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

`enhancement`, `frontend`, `ui`

## Dependencies

Pairs with #029 — ideally shipped together or as an immediate follow-up.
