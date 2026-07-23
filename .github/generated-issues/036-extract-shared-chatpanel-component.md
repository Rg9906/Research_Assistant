# Extract a shared `ChatPanel` component from `PaperSummary` and `WorkspaceDetail`

## Background

`frontend/src/components/PaperSummary.tsx` and `WorkspaceDetail.tsx` each
independently implement a near-identical chat widget: message list state,
`isTyping` state, the same message-rendering loop via `AnswerMessage`, the
same typing-indicator markup, and a nearly identical input form. The two
implementations have already started to drift slightly (`PaperSummary`'s
is a floating overlay with an open/close toggle; `WorkspaceDetail`'s is
inline) even though the actual chat logic (send message, append to
history, call `chatWithWorkspace`, handle errors) is the same.

## Why it matters

This duplication is exactly the kind of thing that makes every subsequent
chat-UI fix (#032 auto-scroll, #033 difficulty selector, #015 streaming)
twice the work and twice the risk of the two surfaces silently diverging
further. Extracting the shared logic now, before three more issues touch
both copies independently, pays for itself almost immediately.

## Proposed solution

Extract a `ChatPanel` component (`frontend/src/components/ChatPanel.tsx`)
taking `workspaceId`, an optional `initialMessages`, and layout props
(inline vs. floating-overlay chrome can stay as a prop or as two thin
wrapper components around a shared core). Move the message state,
send-handler, and rendering loop into it; have both `PaperSummary` and
`WorkspaceDetail` render `<ChatPanel ... />` instead of their own copies.

## Acceptance criteria

- [ ] `PaperSummary.tsx` and `WorkspaceDetail.tsx` both use the same
      underlying `ChatPanel` component for message state, sending, and
      rendering.
- [ ] No behavior change from a user's perspective in either surface.
- [ ] `npx tsc -b` and `npm run build` stay clean.

## Suggested files

- `frontend/src/components/ChatPanel.tsx` (new)
- `frontend/src/components/PaperSummary.tsx`
- `frontend/src/components/WorkspaceDetail.tsx`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

`refactor`, `frontend`

## Dependencies

Recommended before #032, #033, #038, and #015 (all touch this same code
and are cheaper to build once this extraction lands).
