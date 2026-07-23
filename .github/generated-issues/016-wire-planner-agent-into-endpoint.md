# Wire the Planner agent into an actual endpoint

## Background

`src/paperpilot/agent/planner.py` and the whole `src/paperpilot/graph/`
LangGraph pipeline (`compile_agent_graph`, a Planner → Search → Tutor →
Critic loop) are implemented and tested (`tests/test_planner.py`,
`tests/test_graph_flow.py`, `tests/test_graph_integration.py`) but — per
CLAUDE.md §4 and §8 — "not currently wired into the API." This is
explicitly named as "the last inert piece of the agent stack" in both
CLAUDE.md and ROADMAP.md.

## Why it matters

This is the single largest gap between the implemented code and the
product vision in `ProjectIdea.txt`: the Planner is what turns "answer this
one question" into "decompose a research goal into subtasks and drive
search + retrieval from it." It's fully built and tested, just not
reachable by any user-facing flow. Wiring it in is the highest-leverage
feature work available — it activates code that already exists rather
than requiring new agent logic.

## Proposed solution

Add a new endpoint (e.g. `POST /api/workspaces/{id}/plan` or a top-level
`POST /api/research-goals`) that takes a high-level goal string, invokes
`compile_agent_graph()`, and returns the plan's decomposed subtasks and/or
its execution trace. Scope decisions for a maintainer to make explicit in
the PR description (this issue intentionally doesn't prescribe the exact
endpoint shape, since it's a product decision, not just a wiring task):
- Does this endpoint *execute* the full graph (search → retrieve → tutor →
  critic per subtask) synchronously, or just return the decomposition for
  the user to act on step by step?
- How does this interact with an existing workspace vs. creating new ones
  per subtask's discovered papers?
- Should this reuse #014's background-job pattern, given a multi-subtask
  plan is likely to take even longer than a single paper's indexing?

At minimum, ship a version that takes a goal, runs the existing compiled
graph, and returns a structured result — matching the level of ambition
already proven out in `tests/test_graph_integration.py`.

## Acceptance criteria

- [ ] A new endpoint accepts a research goal and invokes the existing
      LangGraph pipeline.
- [ ] The endpoint's response includes the decomposed subtasks and, for
      each, whatever the graph produced (search results, retrieved
      context, tutor answer, critic verdict — per `AgentState`).
- [ ] Failure modes (a subtask's search returning nothing, a subtask's
      papers having no chattable PDF) degrade gracefully rather than
      failing the whole plan.
- [ ] Covered by an integration test building on the existing
      `GraphStubLLM` pattern from `tests/test_graph_integration.py`.
- [ ] CLAUDE.md §4/§8 updated to reflect the Planner's new live status.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/graph/builder.py`, `nodes.py`, `state.py`
- `src/paperpilot/agent/planner.py`
- `src/paperpilot/pipeline.py` (the existing facade LangGraph nodes use)
- `tests/test_graph_integration.py`

## Difficulty

Hard

## Estimated time

3 days

## Labels

`enhancement`, `backend`, `feature`

## Dependencies

None directly, but recommended before #022/#023/#024 per the project's own
roadmap ordering (CLAUDE.md §11 lists Planner-wiring before Comparison/
Roadmap/Quiz).
