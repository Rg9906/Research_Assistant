---
title: "`PDFDownloader` has no protection against SSRF via a redirected/resolved internal IP"
labels: ['security', 'backend', 'bug']
difficulty: Hard
estimate: "1 day"
category: "🔒 Security"
---

# `PDFDownloader` has no protection against SSRF via a redirected/resolved internal IP

**Category:** 🔒 Security

## Background

`PDFDownloader.download_pdf` (`src/paperpilot/document/downloader.py`) validates that a `pdf_url`'s *scheme* is `http`/`https` (good — see CLAUDE.md §7) but never validates the *resolved host*. `pdf_url` values ultimately come from third-party search results (Semantic Scholar's `openAccessPdf`) and directly from the `/api/papers/process` request body, which a client fully controls. A URL like `http://169.254.169.254/latest/meta-data/` or `http://localhost:6379/` passes the scheme check and is fetched exactly like a real PDF link.

## Why it matters

SECURITY.md explicitly lists SSRF via the PDF downloader as in-scope. As written, an attacker who can submit a `pdf_url` (which any user of the public `/api/papers/process` endpoint can) can make the server issue arbitrary GET requests to internal-only hosts and services, potentially reading cloud metadata or reaching internal admin endpoints.

## Proposed solution

Resolve the hostname before connecting and reject requests whose resolved IP falls in a private/loopback/link-local range (RFC 1918, 127.0.0.0/8, 169.254.0.0/16, etc.), and re-check on every redirect hop rather than only the original URL (a public host can still 302 to an internal one).

## Acceptance Criteria

- [ ] `PDFDownloader` rejects a URL that resolves to a private/loopback/link-local IP with a clear error, not a generic failure
- [ ] The same check applies after following a redirect, not just on the initial URL
- [ ] A test simulates a URL resolving to `127.0.0.1` / `169.254.169.254` and asserts the download is refused
- [ ] Legitimate public PDF downloads (arXiv, etc.) are unaffected

## Suggested files

`src/paperpilot/document/downloader.py`, `tests/test_downloader.py`

## Difficulty

Hard

## Estimated time

1 day

## Labels

security, backend, bug

## Dependencies

None
