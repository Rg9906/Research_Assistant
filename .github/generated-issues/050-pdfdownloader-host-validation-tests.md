# Add `PDFDownloader` host-validation tests

## Background

Issue #012 adds a destination-host allowlist/blocklist to `PDFDownloader` to
close the SSRF gap SECURITY.md already flags as in-scope. A security
mitigation without a test is one bad refactor away from silently
disappearing.

## Why it matters

SSRF protections are exactly the kind of code that looks obviously correct,
gets "simplified" by a well-meaning future PR, and quietly stops protecting
anything. A test that specifically targets the private-IP/redirect-bypass
cases is the only durable guarantee.

## Proposed solution

Once #012 lands, add tests to `tests/test_downloader.py` covering: a
`pdf_url` resolving to a loopback/private/link-local address is rejected
before any request is made; a redirect from an allowed host to a disallowed
one is also rejected; legitimate public hosts are unaffected. Use mocked DNS
resolution / a local test server rather than real network calls, consistent
with the existing offline-test discipline.

## Acceptance criteria

- [ ] Private/loopback/link-local destination is rejected with a clear error
- [ ] A redirect to a disallowed host is rejected
- [ ] A legitimate public URL still downloads successfully
- [ ] All tests run fully offline

## Suggested files

- `tests/test_downloader.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

tests, security, backend

## Dependencies

Depends on #012 landing first.
