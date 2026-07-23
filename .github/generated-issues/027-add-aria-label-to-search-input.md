# Add `aria-label` to the DiscoveryFeed search input

## Background

The main search input in `frontend/src/components/DiscoveryFeed.tsx` has a
placeholder but no associated `<label>` or `aria-label`:

```tsx
<input
  value={query}
  onChange={(e) => setQuery(e.target.value)}
  className="..."
  placeholder="Explore complex topics, e.g., 'Evolution of Vision Transformers in Medical Imaging'"
  type="text"
/>
```

A placeholder is not an accessible name — screen readers either announce
nothing meaningful for this field or fall back to the placeholder text in
a way that disappears once text is typed, which is exactly the class of
issue accessibility audits flag first on any form.

## Why it matters

This is the primary entry point of the entire app (the landing page's main
input) — it's the single highest-impact accessibility fix available in the
frontend, and a trivial one to make.

## Proposed solution

```tsx
<label htmlFor="paper-search" className="sr-only">Search for research papers</label>
<input
  id="paper-search"
  aria-label="Search for research papers"
  ...
/>
```

(A visually-hidden `sr-only` label plus `aria-label` is redundant — pick
one; `aria-label` alone is sufficient and matches the pattern already used
elsewhere in this codebase, e.g. `Layout.tsx`'s theme-toggle button.)

## Acceptance criteria

- [ ] The search input has an accessible name via `aria-label` (or an
      associated `<label>`).
- [ ] No visual change to the existing design.
- [ ] Spot-checked with a screen reader or the browser's accessibility
      inspector.

## Suggested files

- `frontend/src/components/DiscoveryFeed.tsx`

## Difficulty

Beginner

## Estimated time

20 minutes

## Labels

`good first issue`, `frontend`, `accessibility`, `ui`

## Dependencies

None.
