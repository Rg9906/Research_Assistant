# Fix path settings not anchored to repo root (`data/`, `storage/` land under `src/`)

## Background

`Settings` in `src/paperpilot/config.py` anchors `.env` lookup to the repo
root explicitly (`_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] /
".env"`) specifically because the documented way to run the API is `cd src
&& uvicorn app.api:app`. But the path fields right below it are plain
relative paths:

```python
data_dir: Path = Path("data")
papers_dir: Path = Path("data/papers")
index_dir: Path = Path("data/indexes")
db_path: Path = Path("data/workspace.db")
...
storage_papers_dir: Path = Path("storage/papers")
```

Relative `Path` objects resolve against the process's current working
directory, not the repo root. Since the documented run command has CWD =
`src/`, every one of these ends up creating `src/data/...` and
`src/storage/...` instead of the repo-root `data/` and `storage/` that
CLAUDE.md §2 documents as the layout. This is not hypothetical — running
the app as documented leaves real downloaded PDFs and a real
`workspace.db` sitting under `src/data/`.

## Why it matters

- Contradicts the repository's own documented layout (CLAUDE.md §2, README
  "Code Layout").
- If the app is ever run from the repo root instead of `src/` (equally
  valid for a namespace package once `PYTHONPATH`/`sys.path` is set), a
  *second*, disconnected `data/`/`storage/` tree is created at the repo
  root — silently losing access to whatever was indexed under `src/data/`.
  Every cache hit becomes a cache miss and every paper looks unprocessed.
  `.gitignore`'s unanchored `data/`/`storage/` patterns happen to catch
  both locations, so this hasn't leaked into git — but it is a real
  data-loss/confusion trap for exactly the "run it a different way" case
  that a new contributor is likely to hit first.

## Proposed solution

Anchor these paths to the repo root the same way `_REPO_ROOT_ENV` already
does, e.g.:

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]

data_dir: Path = _REPO_ROOT / "data"
papers_dir: Path = _REPO_ROOT / "data" / "papers"
index_dir: Path = _REPO_ROOT / "data" / "indexes"
db_path: Path = _REPO_ROOT / "data" / "workspace.db"
storage_papers_dir: Path = _REPO_ROOT / "storage" / "papers"
```

Pydantic allows a `default_factory` for computed defaults if a literal
`Path` expression at class-body time is undesirable — either approach
works as long as the anchor is `parents[2]` from this file, matching
`_REPO_ROOT_ENV`. Keep these overridable via env vars/`.env` exactly as
today (absolute paths supplied there should simply win, as they do now).

## Acceptance criteria

- [ ] `data_dir`, `papers_dir`, `index_dir`, `db_path`, and
      `storage_papers_dir` all resolve to the repo root regardless of the
      process's current working directory.
- [ ] Running `cd src && uvicorn app.api:app` and running from the repo
      root both write to the same `data/` and `storage/` directories.
- [ ] A settings can still override any of these paths via `.env` or an
      environment variable with an absolute path.
- [ ] Existing tests pass; add a test that constructs `Settings` from a
      different CWD (`monkeypatch.chdir`) and asserts the resolved paths
      are still repo-root-relative.

## Suggested files

- `src/paperpilot/config.py`
- `tests/test_models.py` or a new `tests/test_config.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

`bug`, `backend`, `good first issue candidate but has a real footgun — review carefully`

## Dependencies

None.
