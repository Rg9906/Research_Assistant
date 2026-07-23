---
title: "Add a regression test for the PDF-downloader SSRF mitigation once it lands"
labels: ['good first issue', 'tests', 'security']
difficulty: Easy
estimate: "1 hour"
category: "🧪 Testing"
---

# Add a regression test for the PDF-downloader SSRF mitigation once it lands

**Category:** 🧪 Testing

## Background

This is the test-side follow-up to the SSRF hardening issue for `PDFDownloader`: the fix needs a permanent regression test, not just manual verification during the PR that lands it.

## Why it matters

SSRF protections are exactly the kind of security fix that silently regresses during an unrelated refactor (e.g. someone rewrites the download loop for retry-logic reasons and drops the IP check without noticing) unless a test actively guards it.

## Proposed solution

Add a test that mocks DNS resolution (or uses a known-private-IP literal like `http://127.0.0.1/x.pdf`) and asserts `PDFDownloader.download_pdf` refuses it with the new, specific error rather than attempting the request.

## Acceptance Criteria

- [ ] A test asserts a URL resolving to a private/loopback/link-local IP is refused before any request is attempted
- [ ] A test asserts a legitimate public URL is unaffected

## Suggested files

`tests/test_downloader.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, tests, security

## Dependencies

Depends on #6 (SSRF hardening for PDFDownloader)
