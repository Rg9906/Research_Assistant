---
title: "Expose `PaperSession.stream()` via a streaming chat endpoint"
labels: ['feature', 'backend', 'frontend', 'enhancement']
difficulty: Hard
estimate: "3 days"
category: "🚀 Feature"
---

# Expose `PaperSession.stream()` via a streaming chat endpoint

**Category:** 🚀 Feature

## Background

`PaperSession.stream()` (`src/paperpilot/services/paper_chat/session.py`) already implements token-by-token streaming via LlamaIndex's `stream_chat`, but per CLAUDE.md §8/ROADMAP.md, "no endpoint exposes it." Every chat request today waits for the full grounded answer (including any critic retries) before the client sees anything at all.

## Why it matters

This is explicitly called out (ROADMAP.md #3, CLAUDE.md §11 #4) as a real UX problem: "a critic retry currently means a long silent wait." Streaming is the most direct fix, and the hard part (the streaming generator itself) is already written and unused.

## Proposed solution

Add a streaming endpoint (Server-Sent Events or a chunked response) that streams the Tutor's answer tokens as they're generated, falling back gracefully to the existing non-streaming grounded path for the critic audit step (which needs the full answer text before it can run). Update the frontend chat UI (`AnswerMessage.tsx`) to render incrementally.

## Acceptance Criteria

- [ ] A new streaming endpoint exists and streams tokens incrementally rather than waiting for the full answer
- [ ] The frontend renders the streamed answer progressively
- [ ] The critic audit still runs against the complete streamed answer once streaming finishes, preserving the existing grounding guarantee
- [ ] Falls back to the current non-streaming behavior if the client doesn't support SSE

## Suggested files

`src/app/api.py`, `src/paperpilot/services/paper_chat/session.py`, `frontend/src/components/AnswerMessage.tsx`

## Difficulty

Hard

## Estimated time

3 days

## Labels

feature, backend, frontend, enhancement

## Dependencies

Benefits from #11 (background indexing) landing first, but not strictly blocked by it
