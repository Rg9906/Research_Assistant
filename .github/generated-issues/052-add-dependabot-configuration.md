# Add Dependabot configuration

## Background

There is no `.github/dependabot.yml`. The project pulls in a large,
fast-moving dependency surface on the Python side (LangChain, LlamaIndex,
several LLM provider SDKs) and the frontend side (React 19, Vite), several
of which are pinned with wide, unbounded version ranges in `pyproject.toml`
(e.g. `llama-index>=0.10.0` has no upper bound).

## Why it matters

Without Dependabot, dependency updates and security patches only happen when
someone remembers to check manually. For a project accepting outside
contributions, silently drifting dependencies are a common source of "works
on my machine" bug reports.

## Proposed solution

Add `.github/dependabot.yml` configuring both the `pip` ecosystem (root
directory, weekly schedule) and the `npm` ecosystem (`frontend/`, weekly
schedule), plus a `github-actions` entry to keep the workflow actions
(`actions/checkout`, `actions/setup-python`, etc.) current.

## Acceptance criteria

- [ ] `.github/dependabot.yml` exists covering `pip`, `npm`, and `github-actions`
- [ ] First Dependabot PRs appear and pass CI

## Suggested files

- `.github/dependabot.yml` (new)

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, security, ci

## Dependencies

None.
