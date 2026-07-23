---
title: "Tutor/Critic agents re-raise raw exceptions without chaining, discarding useful context"
labels: ['good first issue', 'backend', 'bug']
difficulty: Beginner
estimate: "45 min"
category: "🐛 Bug"
---

# Tutor/Critic agents re-raise raw exceptions without chaining, discarding useful context

**Category:** 🐛 Bug

## Background

`TutorAgent.answer_question` (`src/paperpilot/agent/tutor.py`, line ~156) catches any exception from the chat model call and does `raise e`, which re-raises the same object but loses the natural implicit exception chain a bare `raise` would preserve, and adds a confusing extra frame. `CriticAgent.evaluate_answer` doesn't wrap the `self.chat_model.invoke(...)` call in a try/except at all, so a network hiccup there raises a raw SDK exception with no project-level context, unlike the graceful handling `GroundedQAService.answer` already does around the critic call.

## Why it matters

Inconsistent error handling here makes debugging a live incident harder than it needs to be, and is an easy trap for a new contributor to copy from when writing a new agent.

## Proposed solution

In `tutor.py`, replace `raise e` with a bare `raise` after logging. In `critic.py`, wrap the `invoke` call in a try/except that logs and re-raises with context, matching the pattern `grounded_qa.py` already uses around its own call to the critic.

## Acceptance Criteria

- [ ] `tutor.py`'s exception handler uses a bare `raise` instead of `raise e`
- [ ] `critic.py::evaluate_answer` catches and logs a chat-model invocation failure before re-raising
- [ ] No behavior change for the happy path; existing tests in `tests/test_tutor.py` / `tests/test_critic.py` still pass

## Suggested files

`src/paperpilot/agent/tutor.py`, `src/paperpilot/agent/critic.py`

## Difficulty

Beginner

## Estimated time

45 min

## Labels

good first issue, backend, bug

## Dependencies

None
