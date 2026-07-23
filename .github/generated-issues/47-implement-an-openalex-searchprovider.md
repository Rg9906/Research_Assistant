---
title: "Implement an OpenAlex `SearchProvider`"
labels: ['feature', 'backend', 'enhancement']
difficulty: Medium
estimate: "1 day"
category: "🚀 Feature"
---

# Implement an OpenAlex `SearchProvider`

**Category:** 🚀 Feature

## Background

ROADMAP.md's "Planned / future" section names OpenAlex and Crossref as candidate additional search providers, explicitly "via the existing SearchProvider Protocol." OpenAlex has a free, keyless, well-documented REST API and is a natural first addition — it would also validate that the Protocol design genuinely supports a third provider with no changes to `SearchAgent` or the ranker.

## Why it matters

This is one of the best on-ramp features in the whole roadmap for a contributor who wants to ship something real and visible (a new data source in every search result) without touching the harder RAG/agent internals.

## Proposed solution

Implement `OpenAlexProvider` matching the `SearchProvider` Protocol (see `ArxivProvider`/`SemanticScholarProvider` as references, and the new CONTRIBUTING.md guide from issue #38), register it in `app/utils.py::get_search_agent`, and ensure `PaperSource` (`core/models.py`) already has an `OPENALEX` value (it does) wired through correctly.

## Acceptance Criteria

- [ ] `OpenAlexProvider` implements `SearchProvider` and returns valid `PaperMetadata` for real queries
- [ ] It's registered alongside the existing providers in `get_search_agent`
- [ ] Deduplication (DOI/arXiv id/title similarity) correctly merges OpenAlex results with arXiv/S2 results for the same paper
- [ ] Offline tests mock the OpenAlex HTTP API following the existing provider test pattern

## Suggested files

New `src/paperpilot/search/providers.py` addition (or split into its own module), `src/app/utils.py`, `tests/test_providers.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

feature, backend, enhancement

## Dependencies

None
