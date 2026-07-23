# Add a debounce / submit-guard to the search input

## Background

`DiscoveryFeed.tsx`'s search form calls `runSearch` on submit with no
guard against rapid repeated submissions:

```tsx
const handleSearch = (e?: React.FormEvent) => {
  if (e) e.preventDefault();
  if (!query.trim()) return;
  runSearch(query);
};
```

Nothing prevents a user from hitting Enter repeatedly (or clicking a
"suggested" chip several times fast) and firing multiple concurrent
`/api/search` requests for the same or near-same query — each of which
does real work server-side (embedding, ranking, and a rate-limited
Semantic Scholar call).

## Why it matters

Small polish issue with a real backend cost: every accidental double-submit
is a wasted embedding computation and an extra call against Semantic
Scholar's per-key rate limit — the exact quota the backend already works
hard to protect (`RateLimiter`, retry-on-429 with backoff). A trivial
frontend guard avoids paying for that server-side.

## Proposed solution

Guard `runSearch`/`handleSearch` so a new search can't be triggered while
`loading` is already `true` (the state already exists and is already used
to disable the "Searching..." UI):

```tsx
const handleSearch = (e?: React.FormEvent) => {
  if (e) e.preventDefault();
  if (!query.trim() || loading) return;
  runSearch(query);
};
```

Apply the same guard to `handleSuggestedClick`.

## Acceptance criteria

- [ ] Repeated Enter/submit while a search is in flight does not trigger a
      second concurrent request.
- [ ] The "suggested" quick-search chips are guarded the same way.

## Suggested files

- `frontend/src/components/DiscoveryFeed.tsx`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `frontend`, `enhancement`

## Dependencies

None.
