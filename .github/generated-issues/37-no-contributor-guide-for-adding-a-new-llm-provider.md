---
title: "No contributor guide for adding a new LLM provider"
labels: ['good first issue', 'documentation']
difficulty: Easy
estimate: "1.5 hours"
category: "📚 Documentation"
---

# No contributor guide for adding a new LLM provider

**Category:** 📚 Documentation

## Background

`src/paperpilot/llm/factory.py` is exceptionally well-commented internally about *why* it's structured the way it is, and adding a fourth provider is explicitly designed to be a small, mechanical change ("adding a fourth provider means adding one entry to SUPPORTED_PROVIDERS and one row to each table" — factory.py's own module docstring). None of that mechanical recipe is written down anywhere a contributor would find it *before* diving into the source, though.

## Why it matters

This module is explicitly designed to be extended by contributors (it's referenced by name in the roadmap's "additional search providers" spirit), so a short how-to turns an already-good design into an accessible one.

## Proposed solution

Add a "Adding a new LLM provider" section to CONTRIBUTING.md summarizing the five things a PR needs to touch: `SUPPORTED_PROVIDERS`, `_ENV_KEYS`, a `_langchain_<provider>` builder, a `_llama_<provider>` builder, and the two builder-table entries — linking to `factory.py`'s own docstring for the full rationale.

## Acceptance Criteria

- [ ] CONTRIBUTING.md has a short, accurate "Adding a new LLM provider" walkthrough
- [ ] It correctly lists every file/dict a contributor needs to touch, verified against the current `factory.py`

## Suggested files

`CONTRIBUTING.md`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

good first issue, documentation

## Dependencies

None
