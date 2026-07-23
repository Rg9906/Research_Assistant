# Wire up the workspace delete button in the UI

## Background

The backend fully supports deleting a workspace —
`DELETE /api/workspaces/{workspace_id}` exists in `src/app/api.py` and
correctly cascades (removes the workspace, its paper mappings via SQLite
`ON DELETE CASCADE`, and clears its chat history via
`chat_store.set(workspace_id, [])`). Nothing in the frontend calls it.
`frontend/src/api/client.ts` has no `deleteWorkspace` function at all, and
`ResearchLibrary.tsx`'s workspace cards have no delete affordance — a
workspace, once created, can never be removed from the UI.

## Why it matters

This is a fully-built, tested backend capability with zero frontend
access — the kind of gap that's invisible until a user asks "how do I
delete a workspace I created by mistake?" and the answer is "you can't,
from the app." It's a small, self-contained piece of frontend wiring with
an existing, working API to call.

## Proposed solution

1. Add `deleteWorkspace(workspaceId: string): Promise<void>` to
   `frontend/src/api/client.ts`.
2. Add a delete affordance to each workspace card in `ResearchLibrary.tsx`
   (e.g. a small icon button, consistent with the existing card design
   language), calling `deleteWorkspace` and refreshing the list on
   success.
3. Pair with #038 (confirm before deleting) so this doesn't ship as a
   one-click destructive action with no confirmation step.

## Acceptance criteria

- [ ] A workspace can be deleted from `ResearchLibrary.tsx`.
- [ ] The workspace list refreshes to reflect the deletion.
- [ ] Errors (e.g. network failure) show the existing inline error pattern
      already used elsewhere on this page.
- [ ] Matches the existing card visual design (per CLAUDE.md §9: "keep the
      frontend's current design language").

## Suggested files

- `frontend/src/api/client.ts`
- `frontend/src/components/ResearchLibrary.tsx`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

`good first issue`, `frontend`, `ui`, `enhancement`

## Dependencies

Pairs with #038 (add a confirmation step) — can ship together or #038 as
an immediate follow-up.
