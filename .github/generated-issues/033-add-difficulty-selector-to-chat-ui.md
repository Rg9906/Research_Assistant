# Add a difficulty-level selector to the chat UI

## Background

`ChatMessage.difficulty` is a first-class part of the backend's chat
contract (`src/app/api.py`, forwarded to both the Tutor and Critic — see
`chatWithWorkspace` in `frontend/src/api/client.ts`, which already accepts
a `difficulty` parameter with a default of `'graduate/expert'`), but no UI
anywhere lets the user choose it. Every chat message is sent at the
default level regardless of what the user might want.

## Why it matters

This is a fully-built backend capability with no frontend access — the
same category of gap as #029 (workspace delete). The summary tabs
(`PaperSummary.tsx`) already expose per-level difficulty implicitly via
`SummaryLevel.difficulty`, but chat itself has no equivalent control,
despite the backend explicitly supporting it and the Critic actively
auditing whether an answer matched the requested level.

## Proposed solution

Add a small difficulty selector (e.g. a dropdown or segmented control:
Beginner / Undergraduate / Graduate-Expert — matching #008's proposed
shared `DifficultyLevel` type) to both chat surfaces
(`PaperSummary.tsx`'s floating chat, `WorkspaceDetail.tsx`'s panel),
defaulting to today's `'graduate/expert'` so existing behavior is
unchanged unless the user explicitly changes it. Pass the selected value
through to `chatWithWorkspace`.

## Acceptance criteria

- [ ] A user can select a difficulty level before/while chatting, and
      subsequent messages use that level.
- [ ] Default behavior (no selection made) is unchanged from today.
- [ ] Consistent between `PaperSummary` and `WorkspaceDetail` (ideally via
      the shared `ChatPanel` from #036).

## Suggested files

- `frontend/src/components/PaperSummary.tsx`
- `frontend/src/components/WorkspaceDetail.tsx`
- `frontend/src/components/ChatPanel.tsx` (if #036 lands first)

## Difficulty

Easy

## Estimated time

2 hours

## Labels

`enhancement`, `frontend`, `ui`

## Dependencies

Best done after #036 (shared `ChatPanel`); pairs with #008 (backend
validation for the same values).
