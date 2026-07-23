# Add a `<label>` to the new-workspace-name input

## Background

`frontend/src/components/ResearchLibrary.tsx`'s "create workspace" form has
the same issue as #027 — a placeholder-only input with no accessible name:

```tsx
<input
  type="text"
  value={newWorkspaceName}
  onChange={(e) => setNewWorkspaceName(e.target.value)}
  placeholder="New Workspace Name..."
  className="..."
/>
```

## Why it matters

Same class of gap as #027: a form control with no accessible name is a
basic, easily-caught accessibility failure, and this is one of only two
text inputs on the Research Library page.

## Proposed solution

```tsx
<label htmlFor="new-workspace-name" className="sr-only">New workspace name</label>
<input
  id="new-workspace-name"
  aria-label="New workspace name"
  ...
/>
```

## Acceptance criteria

- [ ] The input has an accessible name.
- [ ] No visual change to the existing design.

## Suggested files

- `frontend/src/components/ResearchLibrary.tsx`

## Difficulty

Beginner

## Estimated time

20 minutes

## Labels

`good first issue`, `frontend`, `accessibility`, `ui`

## Dependencies

None.
