---
title: "Multi-paper Comparison agent over `retrieve_across_papers`"
labels: ['feature', 'backend', 'frontend', 'enhancement']
difficulty: Hard
estimate: "3 days"
category: "🚀 Feature"
---

# Multi-paper Comparison agent over `retrieve_across_papers`

**Category:** 🚀 Feature

## Background

ROADMAP.md's Planned/future section lists "Multi-paper comparison — a Comparison agent over `retrieve_across_papers`" as a named, not-yet-started feature. The retrieval primitive it depends on (`PaperSessionManager.retrieve_across_papers`) already exists and is production-proven via `GroundedQAService`.

## Why it matters

This is the most requested-sounding vision-doc feature (comparing multiple papers side by side is a hallmark research-assistant capability) that's genuinely ready to build on solid existing infrastructure rather than needing new plumbing.

## Proposed solution

Add a `ComparisonAgent` (following the existing Tutor/Critic Protocol-and-injection pattern) that takes a user's comparison question and a set of papers, retrieves relevant chunks from each via `retrieve_across_papers`, and generates a structured comparison (e.g. a per-paper breakdown plus a synthesis) grounded the same way chat answers are. Expose it via a new endpoint.

## Acceptance Criteria

- [ ] A `ComparisonAgent` generates a grounded, citation-backed comparison across 2+ papers in a workspace
- [ ] Refuses (per the existing grounding contract) when the retrieved context doesn't support a comparison claim
- [ ] A new endpoint exposes this to the frontend
- [ ] Tests follow the existing stub-chat-model pattern from `test_tutor.py`/`test_critic.py`

## Suggested files

New `src/paperpilot/agent/comparison.py`, `src/app/api.py`, `frontend/`

## Difficulty

Hard

## Estimated time

3 days

## Labels

feature, backend, frontend, enhancement

## Dependencies

None
