# Add pip caching to the lint workflow

## Background

`.github/workflows/tests.yml` caches pip dependencies
(`cache: pip` under `actions/setup-python`), but `.github/workflows/lint.yml`'s
Python job does not — it only installs `ruff` directly with no cache
configured, and the frontend job in the same file does cache npm
(`cache: npm`). This is an inconsistency between the two workflows and a
missed (small) speed-up.

## Why it matters

Small, but a genuinely free win: consistent caching across workflows makes
CI faster and cheaper, and matching the pattern `tests.yml` already
established avoids the "why does one workflow cache and not the other"
question for future contributors touching CI.

## Proposed solution

Add `cache: pip` (with an appropriate `cache-dependency-path`, e.g.
`pyproject.toml`) to `lint.yml`'s `actions/setup-python` step, matching
`tests.yml`'s existing configuration.

## Acceptance criteria

- [ ] `lint.yml`'s Python job caches pip dependencies
- [ ] Lint workflow run time improves on cache hits (verify in Actions logs)

## Suggested files

- `.github/workflows/lint.yml`

## Difficulty

Beginner

## Estimated time

15 min

## Labels

good first issue, ci

## Dependencies

None.
