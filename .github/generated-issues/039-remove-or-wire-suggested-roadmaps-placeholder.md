# Remove or wire the hardcoded "Suggested Roadmaps" placeholder card

## Background

`DiscoveryFeed.tsx` renders a single, entirely hardcoded "roadmap" card
with no data behind it:

```tsx
<div className="min-w-[280px] ...">
  <span>AI FOUNDATIONS</span>
  <h3>Vision Transformers</h3>
  <p>From original ViT architectures to modern Swin and MAE breakthroughs.</p>
</div>
```

There's exactly one card, always the same content, regardless of what the
user has searched for or what workspaces exist. It isn't clickable and
isn't backed by any state or API call.

## Why it matters

A static, non-interactive placeholder that looks like a real feature (styled
identically to real content elsewhere on the page) reads as a bug to a new
user or contributor — "why does this never change, and why doesn't
clicking it do anything?" It's honest to either remove it until the real
Learning Roadmap feature (#023) exists, or clearly mark it as a preview/
"coming soon" card.

## Proposed solution

Short term: either remove the card and its section entirely, or restyle it
with an explicit "Coming soon" badge so it reads as intentional rather than
broken. Long term: once #023 (Learning Roadmap generator) ships, replace
this section with real, per-user roadmap suggestions.

## Acceptance criteria

- [ ] The "Suggested Roadmaps" section either shows real functionality, is
      removed, or is clearly marked as a preview/placeholder — it no
      longer presents static, non-interactive content as if it were live.

## Suggested files

- `frontend/src/components/DiscoveryFeed.tsx`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `frontend`, `ui`

## Dependencies

Related to #031 (the dead "VIEW ALL" link above this card) and #023 (the
real feature this would eventually become).
