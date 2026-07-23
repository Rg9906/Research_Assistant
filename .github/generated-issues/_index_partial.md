# Generated Issues Index

Auto-generated backlog from the maintainer audit. Each file below is one ready-to-file GitHub issue.

| # | Category | Title | Difficulty | Labels |
|---|---|---|---|---|
| 1 | 🐛 Bug | [`/api/search` accepts an unbounded `limit`, letting one request force a huge ranking pass](01-api-search-accepts-an-unbounded-limit-letting-one-request-fo.md) | Beginner | good first issue, backend, bug |
| 2 | 🐛 Bug | [`GET /api/workspaces/{id}/papers` declares `response_model=List[Any]`, throwing away its schema](02-get-api-workspaces-id-papers-declares-response-model-list-an.md) | Beginner | good first issue, backend, bug |
| 3 | 🐛 Bug | [Auto-created single-paper workspace names can collide between two different papers](03-auto-created-single-paper-workspace-names-can-collide-betwee.md) | Medium | backend, bug |
| 4 | 🐛 Bug | [`PaperSessionManager._active_sessions` grows without bound for the life of the process](04-papersessionmanager-active-sessions-grows-without-bound-for-.md) | Medium | backend, bug, performance |
| 5 | 🐛 Bug | [Tutor/Critic agents re-raise raw exceptions without chaining, discarding useful context](05-tutor-critic-agents-re-raise-raw-exceptions-without-chaining.md) | Beginner | good first issue, backend, bug |
| 6 | 🔒 Security | [`PDFDownloader` has no protection against SSRF via a redirected/resolved internal IP](06-pdfdownloader-has-no-protection-against-ssrf-via-a-redirecte.md) | Hard | security, backend, bug |
| 7 | 🔒 Security | [No rate limiting on any FastAPI endpoint](07-no-rate-limiting-on-any-fastapi-endpoint.md) | Medium | security, backend |
| 8 | 🔒 Security | [CORS origin is hardcoded to `"*"` instead of being configurable](08-cors-origin-is-hardcoded-to-instead-of-being-configurable.md) | Easy | good first issue, security, backend |
| 9 | 🔒 Security | [No automated dependency / vulnerability scanning (Dependabot or CodeQL)](09-no-automated-dependency-vulnerability-scanning-dependabot-or.md) | Beginner | good first issue, security, ci |
| 10 | 🔒 Security | [No maximum request body size configured for the FastAPI app](10-no-maximum-request-body-size-configured-for-the-fastapi-app.md) | Easy | security, backend |
| 11 | ⚡ Performance | [PDF download, parsing, and embedding block the request thread for the whole duration](11-pdf-download-parsing-and-embedding-block-the-request-thread-.md) | Hard | backend, performance, enhancement |
| 12 | ⚡ Performance | [`SemanticScholarProvider` opens a brand-new `httpx.Client` on every request attempt](12-semanticscholarprovider-opens-a-brand-new-httpx-client-on-ev.md) | Easy | good first issue, backend, performance |
| 13 | ⚡ Performance | [No caching of ranked search results for repeated/near-duplicate queries](13-no-caching-of-ranked-search-results-for-repeated-near-duplic.md) | Medium | backend, performance, enhancement |
| 14 | ⚡ Performance | [No HTTP caching headers on the static `/api/summary-levels` catalogue](14-no-http-caching-headers-on-the-static-api-summary-levels-cat.md) | Beginner | good first issue, backend, performance |
| 15 | ⚡ Performance | [`retrieve_across_papers` re-runs retrieval against every paper's index even for single-paper workspaces](15-retrieve-across-papers-re-runs-retrieval-against-every-paper.md) | Easy | backend, performance |
| 16 | 🏗 Refactor | [Remove the vestigial `text_chunks` table and `get_chunks_for_workspace` now that LlamaIndex owns chunk storage](16-remove-the-vestigial-text-chunks-table-and-get-chunks-for-wo.md) | Medium | refactor, backend, tech-debt |
| 17 | 🏗 Refactor | [Extract the repeated try/except → `_fail()` boilerplate in `app/api.py` into a shared decorator](17-extract-the-repeated-try-except-fail-boilerplate-in-app-api-.md) | Medium | good first issue, refactor, backend |
| 18 | 🏗 Refactor | [`PlanStep.node` is a bare `str` instead of a `Literal["search", "tutor"]`](18-planstep-node-is-a-bare-str-instead-of-a-literal-search-tuto.md) | Beginner | good first issue, refactor, backend |
| 19 | 🏗 Refactor | [Standardize FastAPI endpoint response shapes across `app/api.py`](19-standardize-fastapi-endpoint-response-shapes-across-app-api-.md) | Medium | refactor, backend, api |
| 20 | 🏗 Refactor | [Two independent process-local caches (`_active_sessions`, `WorkspaceChatStore`) share the same eviction gap with no shared abstraction](20-two-independent-process-local-caches-active-sessions-workspa.md) | Medium | refactor, backend |
| 21 | 🏗 Refactor | [Document (or eliminate) the loaded-twice embedding model footprint](21-document-or-eliminate-the-loaded-twice-embedding-model-footp.md) | Easy | good first issue, documentation, backend |
| 22 | 🧪 Testing | [`tests/test_workspace.py` under-covers `WorkspaceManager` (5 tests for 8+ public methods)](22-tests-test-workspace-py-under-covers-workspacemanager-5-test.md) | Easy | good first issue, tests, backend |
| 23 | 🧪 Testing | [The LangGraph Planner→Search→Tutor→Critic loop has thin coverage of its retry/loop behavior](23-the-langgraph-planner-search-tutor-critic-loop-has-thin-cove.md) | Medium | tests, backend |
| 24 | 🧪 Testing | [No test covers `PaperSessionManager` session-cache reuse or concurrent access for the same paper](24-no-test-covers-papersessionmanager-session-cache-reuse-or-co.md) | Easy | good first issue, tests, backend |
| 25 | 🧪 Testing | [Wire `pytest-cov` into CI and publish a coverage baseline](25-wire-pytest-cov-into-ci-and-publish-a-coverage-baseline.md) | Easy | good first issue, tests, ci |
| 26 | 🧪 Testing | [No regression test pins the calibrated `rag_similarity_threshold=0.60` value](26-no-regression-test-pins-the-calibrated-rag-similarity-thresh.md) | Medium | tests, backend |
| 27 | 🧪 Testing | [No thread-safety test for `WorkspaceChatStore` under concurrent requests](27-no-thread-safety-test-for-workspacechatstore-under-concurren.md) | Medium | tests, backend |
| 28 | 🧪 Testing | [Set up a frontend test framework (Vitest + React Testing Library) — currently zero frontend tests exist](28-set-up-a-frontend-test-framework-vitest-react-testing-librar.md) | Medium | tests, frontend, ci |
| 29 | 🧪 Testing | [Add a regression test for the `/api/search` `limit` bound once it's added](29-add-a-regression-test-for-the-api-search-limit-bound-once-it.md) | Beginner | good first issue, tests, backend |
| 30 | 🧪 Testing | [Add a regression test for the PDF-downloader SSRF mitigation once it lands](30-add-a-regression-test-for-the-pdf-downloader-ssrf-mitigation.md) | Easy | good first issue, tests, security |
| 31 | 🧪 Testing | [Audit `tests/test_api.py` for missing error-path coverage on every endpoint](31-audit-tests-test-api-py-for-missing-error-path-coverage-on-e.md) | Medium | tests, backend |
| 32 | 🧪 Testing | [No test exercises `GroundedQAService.answer` with `apply_similarity_cutoff=False` returning zero chunks](32-no-test-exercises-groundedqaservice-answer-with-apply-simila.md) | Easy | good first issue, tests, backend |
| 33 | 📚 Documentation | [README.md and CONTRIBUTING.md state a stale test count ("61 tests") that's far below the real suite size](33-readme-md-and-contributing-md-state-a-stale-test-count-61-te.md) | Beginner | good first issue, documentation |
| 34 | 📚 Documentation | [`.env.example` is missing roughly 20 documented `Settings` fields](34-env-example-is-missing-roughly-20-documented-settings-fields.md) | Easy | good first issue, documentation |
| 35 | 📚 Documentation | [No architecture diagram — the two-stack join (Stack A/B) is only described in prose](35-no-architecture-diagram-the-two-stack-join-stack-a-b-is-only.md) | Easy | good first issue, documentation |
| 36 | 📚 Documentation | [No README/CONTRIBUTING mention of FastAPI's auto-generated `/docs` and `/redoc`](36-no-readme-contributing-mention-of-fastapi-s-auto-generated-d.md) | Beginner | good first issue, documentation |
| 37 | 📚 Documentation | [No contributor guide for adding a new LLM provider](37-no-contributor-guide-for-adding-a-new-llm-provider.md) | Easy | good first issue, documentation |
| 38 | 📚 Documentation | [No contributor guide for adding a new search provider (OpenAlex/Crossref are explicitly on the roadmap)](38-no-contributor-guide-for-adding-a-new-search-provider-openal.md) | Easy | good first issue, documentation |
| 39 | 📚 Documentation | [`ProjectIdea.txt` (the vision document) isn't linked from CONTRIBUTING.md](39-projectidea-txt-the-vision-document-isn-t-linked-from-contri.md) | Beginner | good first issue, documentation |
| 40 | 📚 Documentation | [No README badges (build status, license, Python version)](40-no-readme-badges-build-status-license-python-version.md) | Beginner | good first issue, documentation |
| 41 | 📚 Documentation | [No Docker/devcontainer setup — native install requires PyTorch, FAISS, and LlamaIndex build tooling](41-no-docker-devcontainer-setup-native-install-requires-pytorch.md) | Medium | documentation, backend, enhancement |
| 42 | 📚 Documentation | [No FAQ entry explaining why re-processing a paper is sometimes slow again](42-no-faq-entry-explaining-why-re-processing-a-paper-is-sometim.md) | Easy | good first issue, documentation |
| 43 | 📚 Documentation | [Add a one-sentence review/merge-expectations note to CONTRIBUTING.md](43-add-a-one-sentence-review-merge-expectations-note-to-contrib.md) | Beginner | good first issue, documentation |
| 44 | 🚀 Feature | [Wire the Planner agent into a real endpoint — the last inert piece of Stack A](44-wire-the-planner-agent-into-a-real-endpoint-the-last-inert-p.md) | Hard | feature, backend, enhancement |
| 45 | 🚀 Feature | [Expose `PaperSession.stream()` via a streaming chat endpoint](45-expose-papersession-stream-via-a-streaming-chat-endpoint.md) | Hard | feature, backend, frontend, enhancement |
| 46 | 🚀 Feature | [Move PDF processing off the request thread into a background job with pollable status](46-move-pdf-processing-off-the-request-thread-into-a-background.md) | Hard | feature, backend, enhancement |
| 47 | 🚀 Feature | [Implement an OpenAlex `SearchProvider`](47-implement-an-openalex-searchprovider.md) | Medium | feature, backend, enhancement |
| 48 | 🚀 Feature | [Persist `WorkspaceChatStore` to SQLite so conversation memory survives a restart](48-persist-workspacechatstore-to-sqlite-so-conversation-memory-.md) | Hard | feature, backend, enhancement |
| 49 | 🚀 Feature | [Multi-paper Comparison agent over `retrieve_across_papers`](49-multi-paper-comparison-agent-over-retrieve-across-papers.md) | Hard | feature, backend, frontend, enhancement |