# Build a multi-paper Comparison agent

## Background

`ProjectIdea.txt` and ROADMAP.md both describe multi-paper comparison as a
core planned capability ("a Comparison agent over
`retrieve_across_papers`"), and CLAUDE.md §8 lists it under "Not started."
The infrastructure it needs already exists:
`PaperSessionManager.retrieve_across_papers` fans a query across every
paper's index (used today by `GroundedQAService`/`chat_across_papers`),
and the Tutor/Critic contract in `agent/` already knows how to generate
and audit a grounded answer from retrieved chunks.

## Why it matters

This is one of the three "vision features" (alongside #023, #024) that
would meaningfully differentiate PaperPilot from a generic "chat with a
PDF" tool — turning a workspace of related papers into an actual
comparative analysis ("how do these three papers' methodologies differ?",
"which of these reports the strongest baseline?") is a capability most
comparable tools don't offer, and it's a natural extension of
infrastructure that's already built and load-bearing in production.

## Proposed solution

Add a `ComparisonAgent` (following the existing `TutorAgent`/`CriticAgent`
constructor-injection pattern — takes a `BaseChatModel`, is stateless,
built once via `app/utils.py`) that:
1. Takes a workspace's papers and a comparison axis (either user-specified,
   e.g. "compare their evaluation methodology," or a small fixed set of
   default axes: methodology, results, limitations — echoing
   `SummarizerService`'s existing per-level structure).
2. Retrieves relevant chunks *per paper* (not merged across papers — the
   comparison needs to know which chunk came from which paper, unlike the
   merged-by-score retrieval `MultiPaperRetriever` does for chat) via
   `retrieve_across_papers` called once per paper, or a small variant that
   tags results by source paper.
3. Produces a structured comparison (e.g. a per-paper summary of the axis,
   plus an explicit comparative synthesis), grounded and citation-backed
   the same way chat answers are — reuse `nodes_to_chunks`/`build_citations`.
4. Exposed via a new endpoint (e.g.
   `POST /api/workspaces/{id}/compare`) and a new frontend surface (a
   "Compare" view on `WorkspaceDetail`, following that page's existing
   design language per CLAUDE.md §9's "keep the frontend's current design
   language" instruction).

## Acceptance criteria

- [ ] A workspace with 2+ papers can be compared along at least one axis,
      producing a grounded, citation-backed comparison.
- [ ] Citations correctly attribute each point to the paper it came from.
- [ ] Degrades sensibly for a workspace with only one paper (clear message,
      not a crash).
- [ ] Covered by tests using the existing `StubChatModel` pattern.
- [ ] CLAUDE.md §8 updated to reflect this feature's new status.

## Suggested files

- `src/paperpilot/agent/` (new `comparison.py`, following `tutor.py`'s shape)
- `src/paperpilot/services/grounded_qa.py` or a new sibling service
- `src/app/api.py`, `src/app/utils.py`
- `frontend/src/components/WorkspaceDetail.tsx`
- `tests/test_comparison.py` (new)

## Difficulty

Hard

## Estimated time

3 days

## Labels

`feature`, `backend`, `frontend`, `enhancement`

## Dependencies

Recommended after #016 (Planner wiring) per the project's own roadmap
ordering in CLAUDE.md §11, though not a hard technical blocker — this can
be built directly on `retrieve_across_papers` without the Planner.
