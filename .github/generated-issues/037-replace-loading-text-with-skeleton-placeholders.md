# Replace "Loading..." text with skeleton placeholders

## Background

Every loading state in the frontend is a plain text string:
`ResearchLibrary.tsx` (`<p>Loading...</p>`), `WorkspaceDetail.tsx`
(`<p>Loading...</p>`), and similar patterns elsewhere. The rest of the
app's visual design (Material-3-style tokens, glass panels, careful
spacing per `tailwind.config.js`) is considerably more polished than this.

## Why it matters

This is a pure visual-polish gap, but a noticeable one: loading states are
seen on almost every page load, and a plain "Loading..." string reads as
unfinished next to the rest of the app's design system. Skeleton
placeholders (gray blocks shaped like the eventual content) are a
low-effort way to make loading states feel considered rather than
default-browser-text.

## Proposed solution

Add a small reusable `Skeleton` component (a `div` with a pulsing
background using the existing Tailwind token palette, e.g.
`bg-surface-container-high animate-pulse rounded`) and use it in place of
"Loading..." text in `ResearchLibrary.tsx` and `WorkspaceDetail.tsx` (and
anywhere else a bare loading string exists), shaped roughly like the
content that will replace it (e.g. 2–3 card-shaped skeletons for the
workspace grid).

## Acceptance criteria

- [ ] `ResearchLibrary.tsx` and `WorkspaceDetail.tsx` show skeleton
      placeholders instead of plain "Loading..." text while fetching.
- [ ] Skeletons are styled consistently with the existing design tokens and
      work in both light and dark mode.

## Suggested files

- `frontend/src/components/Skeleton.tsx` (new)
- `frontend/src/components/ResearchLibrary.tsx`
- `frontend/src/components/WorkspaceDetail.tsx`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

`good first issue`, `frontend`, `ui`, `enhancement`

## Dependencies

None.
