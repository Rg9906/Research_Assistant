---
title: "No README badges (build status, license, Python version)"
labels: ['good first issue', 'documentation']
difficulty: Beginner
estimate: "30 min"
category: "📚 Documentation"
---

# No README badges (build status, license, Python version)

**Category:** 📚 Documentation

## Background

README.md opens directly with the project description and product tour — there's no badge row (CI status, license, Python/Node version support, latest release) of the kind almost every actively-maintained open-source repository leads with.

## Why it matters

Badges are a tiny effort-to-signal ratio: a visitor's very first glance at the README currently gives no at-a-glance confirmation that CI is green, what license applies, or what Python version is required — all small trust signals that add up when someone is deciding whether to invest time in a project.

## Proposed solution

Add a badge row under the title: GitHub Actions status for `tests.yml`/`lint.yml`, the MIT license badge, a Python 3.11+ badge, and (once issue #25 lands) a coverage badge.

## Acceptance Criteria

- [ ] README.md has a badge row immediately under the title showing CI status, license, and Python version
- [ ] All badges resolve to correct, working URLs

## Suggested files

`README.md`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, documentation

## Dependencies

None
