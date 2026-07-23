---
title: "No FAQ entry explaining why re-processing a paper is sometimes slow again"
labels: ['good first issue', 'documentation']
difficulty: Easy
estimate: "1 hour"
category: "📚 Documentation"
---

# No FAQ entry explaining why re-processing a paper is sometimes slow again

**Category:** 📚 Documentation

## Background

`PaperSessionManager.get_or_create_session`'s fingerprint check (`_is_fingerprint_valid`) invalidates the cached index whenever the PDF hash, embedding model, chunk size/overlap, or LlamaIndex version changes — all sensible, but from a user's perspective, "I clicked process on a paper I already processed and it's slow again" (e.g. after a `.env` change or a dependency bump) has no explanation anywhere in user-facing docs.

## Why it matters

This is exactly the kind of "the code is right but the user is confused" gap that generates avoidable GitHub issues/questions once real users start self-hosting this project.

## Proposed solution

Add a short FAQ section (README.md or a new `docs/faq.md`) explaining the fingerprint cache and the four conditions that invalidate it, in plain language.

## Acceptance Criteria

- [ ] A FAQ entry explains, in user-facing language, why a previously-processed paper can re-index
- [ ] It lists the four fingerprint components in non-technical terms

## Suggested files

`README.md` or new `docs/faq.md`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, documentation

## Dependencies

None
