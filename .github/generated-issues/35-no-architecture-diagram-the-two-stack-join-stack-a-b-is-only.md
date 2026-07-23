---
title: "No architecture diagram — the two-stack join (Stack A/B) is only described in prose"
labels: ['good first issue', 'documentation']
difficulty: Easy
estimate: "2 hours"
category: "📚 Documentation"
---

# No architecture diagram — the two-stack join (Stack A/B) is only described in prose

**Category:** 📚 Documentation

## Background

CLAUDE.md §3 and §4 describe, in careful prose, how Stack A (LangChain agents) and Stack B (LlamaIndex document intelligence) are joined by `GroundedQAService`. This is genuinely the most architecturally important thing to understand about the codebase, and it's currently communicated entirely as text — no diagram anywhere in the repo shows the request flow visually.

## Why it matters

A diagram here would measurably shorten the time it takes a new contributor to build a correct mental model of the system, especially for the request flow in §3 which involves several conditional branches (grounded vs. fallback chat, retry loop, refusal path).

## Proposed solution

Add a diagram (Mermaid works natively in GitHub-rendered Markdown, so no extra tooling is needed) to README.md or CLAUDE.md showing the `/api/workspaces/{id}/chat` request flow: retrieval → tutor → critic → retry/refuse/approve, and the Stack A/Stack B boundary.

## Acceptance Criteria

- [ ] A Mermaid (or equivalent) diagram renders correctly on GitHub in README.md or CLAUDE.md
- [ ] It accurately reflects the current `GroundedQAService.answer` control flow (verified against the actual code)

## Suggested files

`README.md` or `CLAUDE.md`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, documentation

## Dependencies

None
