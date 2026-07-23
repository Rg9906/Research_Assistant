---
title: "No contributor guide for adding a new search provider (OpenAlex/Crossref are explicitly on the roadmap)"
labels: ['good first issue', 'documentation']
difficulty: Easy
estimate: "1.5 hours"
category: "📚 Documentation"
---

# No contributor guide for adding a new search provider (OpenAlex/Crossref are explicitly on the roadmap)

**Category:** 📚 Documentation

## Background

`SearchProvider` (`src/paperpilot/search/providers.py`) is a `typing.Protocol` specifically designed so a new provider (OpenAlex, Crossref — both explicitly named in ROADMAP.md's "Additional search providers") can be added by implementing one `search()` method and injecting it into `SearchAgent`, with zero changes to agent code. This is one of the best-designed extension points in the whole codebase, and it's also one of the few "not started" roadmap items simple enough for an intermediate contributor to actually ship.

## Why it matters

Turning a well-designed-but-undocumented extension point into a guided, approachable task is one of the highest-leverage things this audit can recommend — it converts a roadmap bullet point into something a contributor can pick up in a weekend.

## Proposed solution

Add a "Adding a new search provider" section to CONTRIBUTING.md walking through the `SearchProvider` Protocol, using `ArxivProvider`/`SemanticScholarProvider` as worked examples, and noting where a new provider gets registered (`app/utils.py::get_search_agent`).

## Acceptance Criteria

- [ ] CONTRIBUTING.md has an accurate "Adding a new search provider" walkthrough referencing the real Protocol and an existing implementation as an example
- [ ] It notes the availability-scoring integration point (`search/availability.py`) if the new provider returns PDF links

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
