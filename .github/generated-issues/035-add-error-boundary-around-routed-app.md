# Add an `ErrorBoundary` around the routed app

## Background

There is no React error boundary anywhere in `frontend/src/`. Every route
component (`DiscoveryFeed`, `PaperSummary`, `ResearchLibrary`,
`WorkspaceDetail`) handles its own async errors with local `try`/`catch` +
`error` state, which is good practice for *expected* failures (a failed
fetch), but there's nothing to catch an *unexpected* render-time error
(e.g. a null-pointer on unexpected API response shape) — React unmounts
the entire tree and the user sees a blank white page with no recovery
path.

## Why it matters

A single unhandled error in any one component currently takes down the
whole app rather than degrading gracefully. This matters more than usual
here because several components consume data shapes from a backend that's
actively being extended by this very backlog (new fields, new endpoints) —
an error boundary is cheap insurance against a partially-mismatched
response crashing the whole UI instead of just the one broken view.

## Proposed solution

Add a class-based `ErrorBoundary` component (React error boundaries still
require a class component as of React 19) wrapping the router's `<Outlet
/>` in `Layout.tsx`, rendering a friendly "Something went wrong" state
with a "Reload" action, and logging the error (`console.error` at minimum,
matching the existing error-logging convention used throughout the
codebase).

## Acceptance criteria

- [ ] A deliberately-thrown render error in any routed page shows the
      fallback UI instead of a blank page.
- [ ] The rest of the app (nav, theme toggle) remains usable/visible around
      the fallback where reasonable.
- [ ] `npx tsc -b` and `npm run build` stay clean.

## Suggested files

- `frontend/src/components/ErrorBoundary.tsx` (new)
- `frontend/src/components/Layout.tsx`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

`enhancement`, `frontend`

## Dependencies

None.
