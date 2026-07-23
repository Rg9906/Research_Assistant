# Security Policy

## Supported Versions

PaperPilot AI is in early development (pre-1.0). Security fixes are applied to
the latest `main` branch. There are no long-term-support branches yet.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report them privately using one of the following:

1. **GitHub Security Advisories** (preferred) — go to the repository's
   [**Security → Report a vulnerability**](https://github.com/Rg9906/Research_Assistant/security/advisories/new)
   page to open a private advisory.
2. **Email** — send the details to **rgsaranvishakan2006@gmail.com** with the
   subject line `SECURITY: <short description>`.

Please include as much of the following as you can:

- The type of issue (e.g. SSRF, path traversal, secret leakage, injection).
- The affected file(s) and line(s), or the endpoint involved.
- Step-by-step instructions to reproduce.
- A proof-of-concept, if you have one.
- The potential impact and any suggested remediation.

### What to expect

- **Acknowledgement** within 5 business days.
- An assessment and, if confirmed, a plan and rough timeline for a fix.
- Credit in the release notes / advisory once the fix is published, unless you
  prefer to remain anonymous.

Please give us a reasonable window to release a fix before any public
disclosure. We follow a **coordinated disclosure** approach.

## Scope and known considerations

PaperPilot AI is currently designed to run **locally on `localhost`** and has
**no authentication layer** (see CLAUDE.md §11). If you deploy it beyond a
trusted local machine, you are responsible for adding authentication, rate
limiting, and network controls. Reports about the lack of built-in auth on a
local-only build are already known and tracked, not vulnerabilities in
themselves — but reports about how a specific component behaves once exposed
(e.g. an SSRF vector, a path-traversal in PDF handling, or a way to exfiltrate
API keys) are very welcome.

Areas that are especially security-relevant in this codebase:

- **PDF download** (`src/paperpilot/document/downloader.py`) — URL scheme
  allowlist, size caps, and validation. Server-side request forgery (SSRF) and
  resource-exhaustion vectors are in scope.
- **TLS handling** (`src/paperpilot/net.py`) — the app sends API keys in
  request headers and verifies TLS against the OS trust store. Any change that
  weakens verification (e.g. `verify=False`) is a vulnerability, not a fix.
- **Secret handling** — API keys are loaded from `.env`. Reports of keys being
  logged, echoed to clients, or otherwise leaked are high priority.
- **LLM prompt/response handling** — injection that causes the system to leak
  context it shouldn't, or to take unintended actions.

## Handling secrets

Never commit real API keys, `.env` files, or credentials. If you accidentally
expose a secret, rotate it immediately and notify the maintainer.

Thank you for helping keep PaperPilot AI and its users safe.
