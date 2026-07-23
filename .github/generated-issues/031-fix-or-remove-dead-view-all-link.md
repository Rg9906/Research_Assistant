# Fix or remove the dead "VIEW ALL" link

## Background

`frontend/src/components/DiscoveryFeed.tsx`'s "Suggested Roadmaps" section
header includes a link that goes nowhere:

```tsx
<a className="..." href="#">VIEW ALL</a>
```

`href="#"` is a placeholder that, when clicked, jumps to the top of the
current page — it looks like a functioning link but does nothing useful,
which reads as broken rather than "not yet built."

## Why it matters

Dead links are exactly the kind of small, visible defect that undermines
trust in an otherwise polished UI — a new visitor (or contributor) clicking
around will hit this within the first few seconds on the landing page.

## Proposed solution

Since there's no "all roadmaps" view yet (the "Suggested Roadmaps" section
itself is a hardcoded placeholder pending #039/#023's real Learning
Roadmap feature), the honest fix today is to remove the link entirely (or
disable/style it clearly as "coming soon") until a real destination exists.
Revisit once #023 ships a real roadmap view to link to.

## Acceptance criteria

- [ ] The "VIEW ALL" link either navigates somewhere real, or is removed/
      visually marked as not-yet-available — it no longer behaves like a
      working link that does nothing.

## Suggested files

- `frontend/src/components/DiscoveryFeed.tsx`

## Difficulty

Beginner

## Estimated time

20 minutes

## Labels

`good first issue`, `bug`, `frontend`, `ui`

## Dependencies

Related to #039 (the placeholder card this link sits above) and #023
(the real feature this would eventually link to).
