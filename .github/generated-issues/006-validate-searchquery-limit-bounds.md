# Validate `SearchQuery.limit` bounds

## Background

`SearchQuery` in `src/app/api.py` accepts an unbounded `limit`:

```python
class SearchQuery(BaseModel):
    query: str
    limit: int = 5
```

`POST /api/search` passes this straight to `SearchAgent.discover_papers(...,
top_n=query.limit)` with no minimum or maximum enforced. A client can
request `limit=0` (probably returns nothing useful), a negative number
(undefined behavior downstream), or `limit=100000` (forces the search
providers and ranker to do far more work than the UI ever needs, and — for
`SemanticScholarProvider`, which is rate-limited — burns quota fast).

## Why it matters

This is a classic missing-input-validation gap at an API boundary. It
doesn't matter much for a single trusted local user today, but it's a
resource-exhaustion footgun the moment this API is reachable by anyone
else, and it's the kind of thing a code reviewer on a mature project would
flag on sight.

## Proposed solution

Add Pydantic field constraints:

```python
from pydantic import Field

class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, gt=0, le=50)
```

Pick an upper bound that matches what the UI actually needs (the
`DiscoveryFeed` frontend doesn't currently expose a limit control at all —
it's hardcoded, see `searchPapers` in `frontend/src/api/client.ts`, default
`5`). 50 is a reasonable generous ceiling; adjust if there's a reason to go
higher.

## Acceptance criteria

- [ ] `POST /api/search` with `limit=0`, a negative limit, or a limit above
      the chosen ceiling returns `422 Unprocessable Entity` (FastAPI's
      default for a failed Pydantic validation) instead of being silently
      accepted.
- [ ] `query` rejects an empty string the same way.
- [ ] A test in `tests/test_api.py` (or the new suite from #043) covers the
      validation-error case.

## Suggested files

- `src/app/api.py`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `bug`, `backend`

## Dependencies

None. Pairs naturally with #043 (new `/api/search` endpoint tests).
