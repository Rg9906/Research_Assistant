# Auto-scroll the chat message list to the newest message

## Background

Both chat surfaces (`frontend/src/components/PaperSummary.tsx`'s floating
chat widget and `WorkspaceDetail.tsx`'s workspace chat panel) render
messages in a scrollable container:

```tsx
<div className="flex-1 overflow-y-auto p-4 space-y-4">
  {messages.map((msg, idx) => <AnswerMessage key={idx} message={msg} />)}
  {isTyping && (...)}
</div>
```

Neither container has any logic to scroll to the bottom when a new message
(or the typing indicator) is appended. On a conversation longer than the
visible area, a new reply arrives off-screen and the user has to manually
scroll down to see it.

## Why it matters

This is a basic expectation for any chat UI — every mainstream chat product
auto-scrolls to the newest message. Its absence here is easy to miss during
development (a short test conversation never overflows the container) but
immediately noticeable in real use once a conversation has more than a
handful of turns.

## Proposed solution

Add a ref to the bottom of the message list and scroll it into view
whenever `messages` (or `isTyping`) changes:

```tsx
const bottomRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages, isTyping]);

// ...
{messages.map(...)}
{isTyping && (...)}
<div ref={bottomRef} />
```

Since this logic is identical in both `PaperSummary.tsx` and
`WorkspaceDetail.tsx`, consider implementing it once the shared
`ChatPanel` component (#036) exists, to avoid writing (and later
maintaining) the same fix twice.

## Acceptance criteria

- [ ] Sending a message or receiving a reply scrolls the chat panel to
      show the newest content, in both `PaperSummary` and
      `WorkspaceDetail`.
- [ ] Doesn't fight the user if they've manually scrolled up to read
      earlier history (a common refinement: only auto-scroll if the user
      was already near the bottom — acceptable to skip for a first pass,
      but worth calling out in the PR description).

## Suggested files

- `frontend/src/components/PaperSummary.tsx`
- `frontend/src/components/WorkspaceDetail.tsx`
- `frontend/src/components/ChatPanel.tsx` (if #036 lands first)

## Difficulty

Beginner

## Estimated time

45 minutes

## Labels

`good first issue`, `bug`, `frontend`, `ui`

## Dependencies

Best done after #036 (shared `ChatPanel`) to avoid duplicating the fix;
not a hard blocker if #036 hasn't landed yet.
