---
title: "No maximum request body size configured for the FastAPI app"
labels: ['security', 'backend']
difficulty: Easy
estimate: "2 hours"
category: "🔒 Security"
---

# No maximum request body size configured for the FastAPI app

**Category:** 🔒 Security

## Background

PDF downloads are size-capped (`PDFDownloader.max_download_bytes`, 50MB) but the FastAPI/uvicorn layer itself has no configured limit on the size of an incoming *request body* — e.g. the JSON payload to `/api/papers/process` or `/api/workspaces/{id}/chat`. A very large `authors` list or an enormous `query` string is accepted and processed with no bound.

## Why it matters

This is a small, cheap hardening step in the same spirit as the existing PDF size cap and scheme allowlist — closing an obvious resource-exhaustion vector that's currently open on every JSON endpoint.

## Proposed solution

Add a small ASGI middleware (or a reverse-proxy-level recommendation documented in SECURITY.md, if the app is expected to sit behind one in production) that rejects request bodies over a configurable size with a clean 413.

## Acceptance Criteria

- [ ] Requests with a `Content-Length` (or a streamed body) exceeding a configurable cap are rejected with HTTP 413
- [ ] The cap is configurable via `Settings`
- [ ] A test asserts an oversized request body is rejected

## Suggested files

`src/app/api.py`, `src/paperpilot/config.py`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

security, backend

## Dependencies

None
