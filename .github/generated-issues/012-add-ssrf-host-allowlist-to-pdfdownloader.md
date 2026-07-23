# Add a destination-host allowlist/blocklist to `PDFDownloader` (SSRF)

## Background

`PDFDownloader.download_pdf()` (`src/paperpilot/document/downloader.py`)
already restricts URL **schemes** to `http`/`https` (a documented, resolved
fix — CLAUDE.md §7), which stops `file://`-style local-disk reads. It does
not restrict the **destination host**. `pdf_url` values ultimately
originate from third-party search results (arXiv, Semantic Scholar) today,
but `POST /api/papers/process` accepts `pdf_url` directly as a client-
supplied field with no server-side check that it points at a plausible
academic-PDF host:

```python
class ProcessPaperRequest(BaseModel):
    ...
    pdf_url: Optional[str] = None
```

SECURITY.md explicitly lists this as in-scope: *"Server-side request
forgery (SSRF) ... vectors are in scope"* for `PDFDownloader`. Right now,
nothing stops `pdf_url` from pointing at `http://169.254.169.254/latest/
meta-data/...` (a cloud metadata endpoint), `http://localhost:PORT/...`
(another local service), or any other internal address — the downloader
will happily fetch whatever is at that URL over `http`/`https` and attempt
to parse it as a PDF (which fails validation and is discarded, but only
*after* the request has already been made to wherever it pointed).

## Why it matters

For a single trusted local user, this is low risk. The moment this API is
reachable by more than one person (which SECURITY.md and the roadmap both
anticipate — "authentication for any non-localhost deployment" is an
explicit near-term item), an unauthenticated or lightly-authenticated
`/api/papers/process` becomes a way to make the server issue arbitrary
outbound `GET` requests, probe internal network services, or hit cloud
metadata endpoints — the canonical SSRF impact. This is exactly the kind
of gap SECURITY.md already names as in-scope and worth closing before
deployment guidance changes.

## Proposed solution

Add host-level validation to `PDFDownloader` (or a wrapper called before
it), rejecting:
- Loopback/link-local/private-range destination IPs (resolve the hostname
  and check against `ipaddress.ip_address(...).is_private/.is_loopback/
  .is_link_local`), unless explicitly running in a local-dev mode.
- Optionally, support an explicit allowlist of academic-PDF-serving hosts
  (arxiv.org, common publisher domains, etc.) as a stricter mode, matching
  how `SearchProvider`s already only ever produce URLs from known sources —
  the client-supplied `pdf_url` path in `process_paper` is the only place
  arbitrary hosts can currently enter the system.
- Apply the same check to redirect targets, not just the original URL
  (`urllib.request` follows redirects by default) — a permitted host that
  redirects to an internal address must not bypass the check.

Keep it configurable (e.g. a `Settings.pdf_download_block_private_hosts:
bool = True` with an escape hatch for local development/testing).

## Acceptance criteria

- [ ] A `pdf_url` resolving to a private/loopback/link-local address is
      rejected before any request is made, with a clear error (reusing the
      existing `UnsafeDownloadURLError` pattern).
- [ ] Redirects to a disallowed host are also rejected, not just the
      initial URL.
- [ ] Legitimate public academic-PDF hosts (arXiv, publisher domains) are
      unaffected.
- [ ] `SECURITY.md`'s "Areas that are especially security-relevant" section
      is updated to reflect the new mitigation.
- [ ] Covered by tests (see #050) using a local test server or mocked DNS
      resolution to simulate a private-IP target.

## Suggested files

- `src/paperpilot/document/downloader.py`
- `src/paperpilot/config.py`
- `SECURITY.md`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

`security`, `backend`

## Dependencies

Blocks #050 (host-validation tests).
