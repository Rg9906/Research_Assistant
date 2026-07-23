# Fix dead click affordance on DiscoveryFeed result cards

## Background

Each search result card in `frontend/src/components/DiscoveryFeed.tsx` is
styled with `cursor-pointer`, signaling to the user that the whole card is
clickable:

```tsx
<div key={paper.paper_id} className="group ... cursor-pointer">
  ...
  <button onClick={(e) => handleReadSummary(paper, e)}>READ SUMMARY ...</button>
</div>
```

But the outer `<div>` has no `onClick` handler at all — only the small
"READ SUMMARY" button at the bottom actually navigates anywhere. Clicking
anywhere else on the card (the title, the author list, the empty space)
does nothing, despite the cursor telling the user it's interactive.

## Why it matters

This is a small but real UX papercut: the visual affordance promises
click-anywhere behavior that doesn't exist, which reads as "broken" to a
user who naturally clicks the title of a search result (the most common
interaction pattern for any search UI) and gets no response.

## Proposed solution

Either:
1. Add an `onClick` to the outer card that calls the same navigation as
   "READ SUMMARY" (`handleReadSummary`), with
   `e.stopPropagation()` retained on the button itself so its own click
   doesn't double-navigate — the simplest fix, matching
   `ResearchLibrary.tsx`'s workspace cards, which already do exactly this
   (`onClick={() => navigate(...)}` on the outer card).
2. Or remove `cursor-pointer` from the outer card if only the button should
   be clickable, and rely on the button alone as the affordance.

Option 1 matches this app's existing pattern elsewhere and is the more
user-friendly choice.

## Acceptance criteria

- [ ] Clicking anywhere on a result card (not just the "READ SUMMARY"
      button) navigates to the paper's summary page.
- [ ] The button no longer causes a duplicate/conflicting navigation call.
- [ ] No visual change.

## Suggested files

- `frontend/src/components/DiscoveryFeed.tsx`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `bug`, `frontend`, `ui`

## Dependencies

None.
