# Add unit tests for `app/utils.py` dependency wiring

## Background

`src/app/utils.py` holds every `lru_cache`-backed singleton getter
(`get_db_manager`, `get_search_agent`, `get_paper_session_manager`,
`get_workspace_chat_store`, etc.) and `get_optional_grounded_qa_service`
(`:112`), which is the function responsible for the documented graceful
degradation: if the agents' chat model can't be built, the app falls back to
the plain LlamaIndex chat path instead of crashing. None of this file has
direct unit tests today — it's only exercised indirectly through
`test_api.py`'s happy-path fixtures.

## Why it matters

`get_optional_grounded_qa_service` is the single seam that decides whether
every chat request gets the audited Tutor/Critic path or the fallback path.
If it silently always returned `None` (e.g. because of a broken provider
config check), the whole grounded-QA feature would quietly stop running in
production while every existing test — which overrides the dependency
directly — would keep passing.

## Proposed solution

Add `tests/test_app_utils.py` covering: `get_optional_grounded_qa_service`
returns `None` when no LLM provider can be built and returns a service
instance when one can (using the `StubChatModel` pattern); `WorkspaceChatStore`
correctly scopes history per `workspace_id` and doesn't leak between them
(the exact bug class CLAUDE.md §7 documents as historically fixed); the
`lru_cache` singletons return the same instance across calls.

## Acceptance criteria

- [ ] `get_optional_grounded_qa_service`'s both branches (available/unavailable)
      are tested
- [ ] `WorkspaceChatStore` isolation between two workspace IDs is tested
- [ ] At least one singleton getter's caching behavior is asserted

## Suggested files

- `tests/test_app_utils.py` (new)
- `src/app/utils.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

tests, backend

## Dependencies

None.
