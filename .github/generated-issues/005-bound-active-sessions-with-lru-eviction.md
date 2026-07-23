# Bound `PaperSessionManager._active_sessions` with LRU eviction

## Background

`PaperSessionManager` (`src/paperpilot/services/paper_chat/session.py`)
caches one `PaperSession` per paper in `self._active_sessions: Dict[str,
PaperSession]` for the lifetime of the process, and never evicts:

```python
def get_or_create_session(self, metadata, pdf_url=None) -> PaperSession:
    paper_id_str = str(metadata.paper_id)
    if paper_id_str in self._active_sessions:
        return self._active_sessions[paper_id_str]
    ...
    session = PaperSession(metadata=metadata, paper_dir=paper_dir, index=index)
    self._active_sessions[paper_id_str] = session
    return session
```

Each `PaperSession` holds a loaded `VectorStoreIndex` (embeddings for every
chunk of that paper, held in memory) plus, optionally, a
`SentenceTransformerRerank` postprocessor. `PaperSessionManager` itself is
an `lru_cache(maxsize=1)` singleton (`app/utils.py`), so this dictionary
lives for the process's entire uptime.

## Why it matters

A long-running server that processes many distinct papers over time (the
intended use case — this is a research assistant meant to accumulate a
library) will accumulate one in-memory vector index per paper forever, with
no upper bound. On a machine with many papers processed across weeks of
uptime, this is unbounded memory growth that only a process restart clears.
This isn't a problem at today's single-user scale, but it's exactly the
kind of latent issue that turns into a production incident the first time
someone runs this as a long-lived shared service.

## Proposed solution

Replace the plain `dict` with a bounded LRU structure (e.g.
`functools.lru_cache`-style eviction via `collections.OrderedDict`, or the
`cachetools.LRUCache` library) with a configurable max size (a new
`Settings` field, e.g. `paper_session_cache_size`, default something
reasonable like 20–50). On eviction, nothing needs to be persisted (the
index is already persisted to disk under `storage/papers/paper_<id>/` —
eviction just means the next request for that paper pays the "load from
disk" cost instead of "already in memory," which `get_or_create_session`
already handles via the fingerprint-check path).

## Acceptance criteria

- [ ] `_active_sessions` never exceeds a configurable maximum size.
- [ ] Evicting a session and then requesting that paper again transparently
      reloads it from disk (existing fingerprint-cache-hit code path) with
      no user-visible error.
- [ ] A test creates more sessions than the configured cap and asserts the
      least-recently-used one was evicted while a fresh request for it
      still succeeds.
- [ ] Document the new setting in `.env.example` (see #057).

## Suggested files

- `src/paperpilot/services/paper_chat/session.py`
- `src/paperpilot/config.py`
- `tests/test_paper_chat.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

`performance`, `backend`

## Dependencies

None.
