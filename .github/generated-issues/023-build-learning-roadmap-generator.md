# Build a Learning Roadmap generator

## Background

`ProjectIdea.txt` describes generating a study path across a set of papers
as a core vision feature; ROADMAP.md lists "Learning roadmaps — generate a
study path across a set of papers" under planned/future work, and CLAUDE.md
§8 marks it "Not started." (Note: `DiscoveryFeed.tsx` already has a
hardcoded, non-functional "Suggested Roadmaps" placeholder card — see issue
#039 — which this feature would eventually replace with real data.)

## Why it matters

This is the feature that turns a workspace from "a folder of papers" into
"a structured way to learn a topic" — ordering papers by prerequisite
relationships (using each paper's own `SummarizerService`-generated
"Prerequisites" summary level, which already exists) and producing a
recommended reading order with rationale. It's a natural second phase
after Comparison (#022): both operate over a workspace's full paper set
and both are grounded-generation tasks the existing Tutor/Critic
infrastructure can support.

## Proposed solution

Add a `RoadmapAgent`/service that:
1. For each paper in a workspace, retrieves (or reuses cached) content for
   the existing `prerequisites` and `contributions` summary levels
   (`SummarizerService`/`SUMMARY_LEVELS` already define these).
2. Produces an ordered reading sequence with a one-line rationale per step
   ("read X before Y because Y builds on X's attention mechanism"),
   grounded in the papers' own stated prerequisites/contributions rather
   than the model's general knowledge.
3. Exposed via a new endpoint (e.g. `POST /api/workspaces/{id}/roadmap`)
   and rendered in the frontend — this is the natural real replacement for
   the hardcoded "Suggested Roadmaps" card in `DiscoveryFeed.tsx` (#039),
   moved to a workspace-scoped view once a user has a set of papers to
   order.

## Acceptance criteria

- [ ] Given a workspace with 2+ indexed papers, produces an ordered
      reading sequence with a stated rationale per step.
- [ ] Rationale is grounded in the papers' own content (via existing
      summary levels or fresh retrieval), not generic LLM knowledge.
- [ ] Degrades sensibly for a single-paper workspace.
- [ ] Covered by tests using the `StubChatModel`/stub summarizer pattern.
- [ ] CLAUDE.md §8 updated.

## Suggested files

- `src/paperpilot/agent/` or `src/paperpilot/services/` (new module)
- `src/app/api.py`, `src/app/utils.py`
- `frontend/src/components/WorkspaceDetail.tsx`, `DiscoveryFeed.tsx`
- `tests/` (new test file)

## Difficulty

Hard

## Estimated time

3 days

## Labels

`feature`, `backend`, `frontend`, `enhancement`

## Dependencies

Recommended after #016 (Planner wiring), per roadmap ordering. Can share
groundwork with #022 (both retrieve per-paper rather than merged-by-score).
