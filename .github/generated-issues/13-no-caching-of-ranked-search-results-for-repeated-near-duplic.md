---
title: "No caching of ranked search results for repeated/near-duplicate queries"
labels: ['backend', 'performance', 'enhancement']
difficulty: Medium
estimate: "3 hours"
category: "⚡ Performance"
---

# No caching of ranked search results for repeated/near-duplicate queries

**Category:** ⚡ Performance

## Background

`PaperRanker.rank_papers` (`src/paperpilot/search/ranker.py`) re-embeds every candidate paper's title+abstract on every `/api/search` call, even if the exact same query was just run (e.g. a user re-opening the discovery feed, or refreshing). There is no result cache at any layer.

## Why it matters

For a query that returns the same candidate set repeatedly (common during a single research session), this is pure repeated work — embedding N candidates costs the same every time, and it's on the hot path for every page load of the discovery feed.

## Proposed solution

Add a small time-boxed cache (e.g. `cachetools.TTLCache`, keyed on the normalized query string) in front of `SearchAgent.discover_papers`, with a short TTL (a few minutes) so results stay fresh but repeated hits within a session are free.

## Acceptance Criteria

- [ ] Two identical searches within the TTL window hit the cache instead of re-querying providers and re-embedding
- [ ] The TTL is configurable via `Settings`
- [ ] A test asserts a second identical call doesn't re-invoke the embedding engine

## Suggested files

`src/paperpilot/search/agent.py`, `src/paperpilot/config.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

backend, performance, enhancement

## Dependencies

None
