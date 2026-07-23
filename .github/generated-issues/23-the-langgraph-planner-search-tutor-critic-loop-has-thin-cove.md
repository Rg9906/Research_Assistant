---
title: "The LangGraph Planner→Search→Tutor→Critic loop has thin coverage of its retry/loop behavior"
labels: ['tests', 'backend']
difficulty: Medium
estimate: "3 hours"
category: "🧪 Testing"
---

# The LangGraph Planner→Search→Tutor→Critic loop has thin coverage of its retry/loop behavior

**Category:** 🧪 Testing

## Background

`tests/test_graph_integration.py` (3 tests), `tests/test_graph_flow.py` (6 tests), and `tests/test_planner.py` (3 tests) cover the LangGraph pipeline in `src/paperpilot/graph/`, but it's not clear from the test count that the *loop* behavior in `critic_router` (`graph/builder.py`) — specifically, retrying `tutor` up to 3 times on rejection and then exiting via `END` once exhausted — has a dedicated test forcing all 3 retries and asserting the graph actually terminates rather than looping forever.

## Why it matters

This loop is the one piece of graph logic most likely to regress silently into an infinite loop or an off-by-one exit condition, and it's exactly the code path that will get exercised the moment the Planner agent is wired into production (CLAUDE.md §11, ROADMAP.md "Wire in the Planner agent").

## Proposed solution

Add a test using a stub critic that always rejects, driving `critic_router` through all 3 retries, and assert the graph terminates at `END` rather than continuing to loop, plus a test for the multi-step (`search` + `tutor`) plan path completing end-to-end with a stub search agent.

## Acceptance Criteria

- [ ] A test forces 3 consecutive critic rejections and asserts the graph exits at `END` instead of looping
- [ ] A test exercises a two-step plan (one `search` step, one `tutor` step) end-to-end using stubs
- [ ] Both tests stay fully offline using the existing `StubChatModel`/`GraphStubLLM` pattern

## Suggested files

`tests/test_graph_integration.py`, `tests/test_graph_flow.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

tests, backend

## Dependencies

None
