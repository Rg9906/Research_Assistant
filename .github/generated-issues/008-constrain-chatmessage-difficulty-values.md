# Constrain `ChatMessage.difficulty` to known values

## Background

`ChatMessage.difficulty` (`src/app/api.py`) is a free-form string forwarded
verbatim into both the Tutor and Critic prompts:

```python
class ChatMessage(BaseModel):
    query: str
    difficulty: str = "graduate/expert"
```

The values that are actually meaningful are already enumerated elsewhere —
`SummaryLevel.difficulty` in `services/summarizer.py` uses exactly three:
`"undergraduate"`, `"beginner"`, `"graduate/expert"`. There's nothing
stopping a client from sending `difficulty: "ignore all previous
instructions"` or any other arbitrary string, which then flows straight
into an LLM prompt.

## Why it matters

Two independent reasons to fix this: (1) correctness — an unrecognized
difficulty string silently produces whatever the Tutor/Critic prompt
templates do with an unexpected value, with no validation error to tell
the caller they made a typo; (2) it's the one place in the request contract
where arbitrary client text reaches a prompt with no constraint, which is
worth closing even in a single-user local app, since the frontend itself
never offers more than the default today (see #033).

## Proposed solution

Define a shared `Literal` or `Enum` for the three difficulty levels (a good
place is `paperpilot/core/models.py`, so both the FastAPI request model and
`SummaryLevel` can reference the same type), and use it in `ChatMessage`:

```python
from typing import Literal

DifficultyLevel = Literal["beginner", "undergraduate", "graduate/expert"]

class ChatMessage(BaseModel):
    query: str
    difficulty: DifficultyLevel = "graduate/expert"
```

## Acceptance criteria

- [ ] `POST /api/workspaces/{id}/chat` with an unrecognized `difficulty`
      value returns `422` instead of being silently forwarded.
- [ ] The three known values continue to work exactly as before.
- [ ] `SummaryLevel.difficulty` and `ChatMessage.difficulty` reference the
      same defined type so they can't drift.
- [ ] Existing tests (`tests/test_api.py::TestChatEndpoint`) still pass.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/core/models.py`
- `src/paperpilot/services/summarizer.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

`good first issue`, `backend`, `refactor`

## Dependencies

None.
