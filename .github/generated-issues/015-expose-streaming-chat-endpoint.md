# Expose `PaperSession.stream()` via a streaming chat endpoint

## Background

`PaperSession.stream()` (`src/paperpilot/services/paper_chat/session.py`)
already implements token-by-token streaming over LlamaIndex's
`stream_chat`, but no FastAPI endpoint exposes it — `ROADMAP.md` and
CLAUDE.md §11 both list this as planned work ("Streaming responses ...
`PaperSession.stream()` exists but no endpoint exposes it; a critic retry
currently means a long silent wait").

## Why it matters

Today, `POST /api/workspaces/{id}/chat` is a single request/response that
can involve up to three sequential LLM calls (tutor generation, critic
audit, and a retried tutor generation on rejection — see
`GroundedQAService.answer`), all before the client sees anything. The user
stares at a typing indicator for however long that whole chain takes, with
no partial feedback. Streaming the tutor's own generation would make the
dominant-case latency (no critique rejection) feel dramatically faster
without changing the underlying grounding/audit logic.

## Proposed solution

Add a streaming variant of the chat endpoint (e.g.
`POST /api/workspaces/{id}/chat/stream`, using FastAPI's
`StreamingResponse` with Server-Sent Events or chunked text). Two
reasonable scope options for the initial version:
1. **Minimal**: stream only the plain LlamaIndex chat path
   (`chat_across_papers`/`PaperSession.stream()`), leaving the
   Tutor/Critic grounded path as request/response for now (the critic
   fundamentally needs the full answer before it can audit it, so
   streaming *that* path meaningfully needs more design — e.g. stream the
   tutor's tokens live, then append a final "audit" event once the critic
   finishes).
2. **Full**: stream the Tutor's generation as it's produced, then emit the
   citations/audit verdict as a final SSE event once the critic completes.
   This preserves the grounding contract while giving the user immediate
   token-level feedback.

Whichever scope is chosen, the frontend's chat UI (`PaperSummary.tsx`,
`WorkspaceDetail.tsx`) needs to consume an event stream instead of a single
JSON response — worth coordinating with #036 (extracting a shared
`ChatPanel` component), since both surfaces share this logic.

## Acceptance criteria

- [ ] A streaming endpoint returns partial tokens as they're generated.
- [ ] Citations and the approved/refused verdict are still delivered (as a
      final event) even though the answer text streamed incrementally.
- [ ] The non-streaming endpoint continues to work unchanged for existing
      clients.
- [ ] Frontend chat UI renders streamed tokens progressively.
- [ ] Covered by a test exercising the streaming response shape.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/services/paper_chat/session.py`
- `src/paperpilot/services/grounded_qa.py`
- `frontend/src/components/PaperSummary.tsx`, `WorkspaceDetail.tsx`

## Difficulty

Medium

## Estimated time

1 day

## Labels

`enhancement`, `backend`, `frontend`

## Dependencies

None. Recommended after #036 (shared `ChatPanel`) so streaming is wired
once, not twice.
