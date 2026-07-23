---
title: "`PlanStep.node` is a bare `str` instead of a `Literal["search", "tutor"]`"
labels: ['good first issue', 'refactor', 'backend']
difficulty: Beginner
estimate: "30 min"
category: "🏗 Refactor"
---

# `PlanStep.node` is a bare `str` instead of a `Literal["search", "tutor"]`

**Category:** 🏗 Refactor

## Background

`PlanStep` (`src/paperpilot/agent/planner.py`) types `node: str` even though the system prompt, `graph/builder.py::planner_router`, and `graph/nodes.py` all only ever branch on the literal strings `"search"` and `"tutor"`. If the LLM emits any other value in that field, Pydantic validation on `ResearchPlan` currently accepts it silently, and it only fails later, confusingly, inside the graph router.

## Why it matters

This is exactly the kind of place Pydantic's contract-layer role (CLAUDE.md §6: "Pydantic as the contract layer") is supposed to prevent — a malformed value should fail loudly and immediately at the model boundary, not silently propagate into graph routing logic.

## Proposed solution

Change `node: str` to `node: Literal["search", "tutor"]`. `PlannerAgent.generate_plan`'s existing parse-failure fallback path already handles the case where the LLM's JSON doesn't validate, so this tightening is covered by the same fallback that already exists for malformed output.

## Acceptance Criteria

- [ ] `PlanStep.node` is typed `Literal["search", "tutor"]`
- [ ] An LLM response with an invalid `node` value now fails Pydantic validation and falls through to the existing fallback plan instead of reaching the graph router
- [ ] `tests/test_planner.py` gains a case asserting this

## Suggested files

`src/paperpilot/agent/planner.py`, `tests/test_planner.py`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, refactor, backend

## Dependencies

None
