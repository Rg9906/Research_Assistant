---
title: "Wire the Planner agent into a real endpoint — the last inert piece of Stack A"
labels: ['feature', 'backend', 'enhancement']
difficulty: Hard
estimate: "3 days"
category: "🚀 Feature"
---

# Wire the Planner agent into a real endpoint — the last inert piece of Stack A

**Category:** 🚀 Feature

## Background

The LangGraph Planner→Search→Selection→Retriever→Tutor→Critic pipeline (`src/paperpilot/graph/`) is fully built, tested, and compilable via `compile_agent_graph`, but per CLAUDE.md §4/§8 and ROADMAP.md, it is "not currently wired into the API" — no endpoint invokes it. This is explicitly ROADMAP.md's #2 priority ("Wire in the Planner agent").

## Why it matters

This is the single most impactful roadmap item for the project's stated vision (CLAUDE.md §1: "intelligence comes from planning, retrieval, memory, reasoning... not from prompting a model harder") — right now the Planner is fully implemented and completely unused, which is an odd place for the project's flagship differentiator to sit.

## Proposed solution

Add a new endpoint (e.g. `POST /api/workspaces/{id}/plan-and-answer` or similar) that builds `AgentNodes` from the existing `DocumentPipeline`/`SearchAgent`/`TutorAgent`/`CriticAgent` singletons, compiles the graph via `compile_agent_graph`, and invokes it for a user's multi-step query, returning the final compiled answer. Decide (and discuss in the issue before implementing) whether this replaces or supplements the existing `/chat` endpoint — this is an architecture-level decision per CONTRIBUTING.md's guidance.

## Acceptance Criteria

- [ ] A new endpoint invokes the compiled LangGraph pipeline for a real user query
- [ ] The endpoint handles both single-step (pure `tutor`) and multi-step (`search` + `tutor`) plans
- [ ] The frontend has at least a minimal way to trigger this path (even if behind a feature flag or a separate UI entry point) so it can be manually verified end-to-end
- [ ] New tests cover the endpoint using the existing stub-based graph test patterns

## Suggested files

`src/app/api.py`, `src/app/utils.py`, `src/paperpilot/graph/`, `frontend/`

## Difficulty

Hard

## Estimated time

3 days

## Labels

feature, backend, enhancement

## Dependencies

None
