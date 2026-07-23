---
title: "CORS origin is hardcoded to `"*"` instead of being configurable"
labels: ['good first issue', 'security', 'backend']
difficulty: Easy
estimate: "1 hour"
category: "🔒 Security"
---

# CORS origin is hardcoded to `"*"` instead of being configurable

**Category:** 🔒 Security

## Background

`src/app/api.py` sets `allow_origins=["*"]` with a code comment explaining this is intentional for local dev (no credentialed requests, so it's spec-valid). That reasoning holds for `localhost`, but the setting isn't exposed anywhere, so anyone following SECURITY.md's advice to deploy "beyond a trusted local machine" has no obvious knob to lock CORS down to their own frontend's origin — they'd have to edit `api.py` directly.

## Why it matters

Making this configurable (rather than editable-only) is a small change that meaningfully lowers the chance someone ships a public deployment with a wildcard CORS origin simply because there was no easier option.

## Proposed solution

Add a `Settings.cors_allowed_origins: list[str]` (default `["*"]` to preserve today's behavior) and wire it into `CORSMiddleware`. Document the setting in `.env.example` and in SECURITY.md's deployment section.

## Acceptance Criteria

- [ ] `CORSMiddleware` reads its `allow_origins` from a new `Settings` field
- [ ] Default value preserves current `"*"` behavior for local dev
- [ ] `.env.example` documents the new setting with a one-line deployment warning
- [ ] SECURITY.md's "Scope and known considerations" section mentions the new knob

## Suggested files

`src/app/api.py`, `src/paperpilot/config.py`, `.env.example`, `SECURITY.md`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, security, backend

## Dependencies

None
