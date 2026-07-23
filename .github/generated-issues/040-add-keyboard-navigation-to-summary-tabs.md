# Add keyboard navigation to the summary tab selector

## Background

`PaperSummary.tsx`'s tab selector (Abstract, Quick, Beginner, Technical,
Contributions, ...) renders each tab as a `<button>` in a horizontal
scrollable row:

```tsx
{allTabs.map(tab => (
  <button key={tab.id} onClick={() => handleTabClick(tab.id)} className="...">
    {tab.label}
  </button>
))}
```

Each button is individually focusable via Tab, but there's no
arrow-key/roving-tabindex behavior, and the buttons have no `role="tab"`/
`aria-selected` semantics — a screen reader announces them as a list of
plain buttons rather than a tab group, and keyboard users must Tab through
every single tab individually rather than using arrow keys to move between
them (the standard interaction pattern for a tablist, per WAI-ARIA).

## Why it matters

This is the primary content-navigation control on the paper detail page —
worth bringing up to the standard accessible-tabs pattern (`role="tablist"`
on the container, `role="tab"` + `aria-selected` on each button,
`role="tabpanel"` on the content area, and arrow-key navigation between
tabs) both for screen-reader users and for keyboard-only users who'd
benefit from arrow-key switching.

## Proposed solution

Apply the standard ARIA tabs pattern:

```tsx
<div role="tablist" aria-label="Summary views">
  {allTabs.map(tab => (
    <button
      key={tab.id}
      role="tab"
      aria-selected={activeTab === tab.id}
      tabIndex={activeTab === tab.id ? 0 : -1}
      onClick={() => handleTabClick(tab.id)}
      onKeyDown={(e) => handleTabKeyDown(e, tab.id)}
      ...
    >
      {tab.label}
    </button>
  ))}
</div>
<article role="tabpanel" aria-label={activeTabMeta?.label}>...</article>
```

with a small `handleTabKeyDown` implementing left/right arrow-key movement
between tabs (wrapping at the ends), following the
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).

## Acceptance criteria

- [ ] Tabs expose `role="tab"`/`aria-selected` and the content area exposes
      `role="tabpanel"`.
- [ ] Arrow keys move focus/selection between tabs when a tab has focus.
- [ ] Existing click behavior is unchanged.

## Suggested files

- `frontend/src/components/PaperSummary.tsx`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

`accessibility`, `frontend`, `ui`

## Dependencies

None.
