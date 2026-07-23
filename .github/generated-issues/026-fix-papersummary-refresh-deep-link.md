# Fix `PaperSummary` breaking on page refresh or a direct link

## Background

`frontend/src/components/PaperSummary.tsx` gets its paper data exclusively
from React Router navigation state, set when a user clicks through from
`DiscoveryFeed`:

```tsx
// DiscoveryFeed.tsx
navigate(`/paper/${paper.paper_id}`, { state: { paper } });

// PaperSummary.tsx
const { state } = useLocation();
const paper = state?.paper as Paper | undefined;
if (!paper) {
  return <div>...Paper not found...<button onClick={() => navigate('/')}>Go back</button></div>;
}
```

Router `state` is only present when navigation happened via `<Link>`/
`navigate()` *within* the running app. Refreshing the page, opening
`/paper/:paperId` in a new tab, or sharing the URL with someone else all
land on this route with no `state`, and the page renders "Paper not found"
even though the paper is fully processed, indexed, and sitting in the
database.

## Why it matters

This makes every paper page effectively unbookmarkable, unshareable, and
unrefreshable — a real, everyday UX failure for a page whose whole purpose
is to be a persistent home for "your notes and chat about this paper."

## Proposed solution

Fetch the paper by ID from the new `GET /api/papers/{paper_id}` endpoint
(#011) whenever `state.paper` isn't present, using the `:paperId` route
param that's already in the URL:

```tsx
const { paperId } = useParams();
const [paper, setPaper] = useState<Paper | undefined>(state?.paper);
const [loading, setLoading] = useState(!state?.paper);

useEffect(() => {
  if (paper || !paperId) return;
  fetchPaperById(paperId)
    .then(setPaper)
    .catch(() => setPaper(undefined))
    .finally(() => setLoading(false));
}, [paperId, paper]);
```

(`fetchPaperById` is a small new function in `frontend/src/api/client.ts`
calling the new endpoint.) Keep the existing `state.paper` fast path for
the common click-through case — this only adds a fallback fetch, not a
behavior change for the existing flow.

## Acceptance criteria

- [ ] Refreshing `/paper/:paperId` (or opening it directly) loads the
      correct paper instead of showing "Paper not found."
- [ ] The existing click-through-from-search flow is unchanged (no extra
      network request when `state.paper` is already present).
- [ ] A genuinely unknown/deleted paper ID still shows a clear
      "not found" state.
- [ ] `npx tsc -b` and `npm run build` stay clean.

## Suggested files

- `frontend/src/components/PaperSummary.tsx`
- `frontend/src/api/client.ts`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

`bug`, `frontend`

## Dependencies

Requires #011 (`GET /api/papers/{paper_id}` endpoint) to exist first.
