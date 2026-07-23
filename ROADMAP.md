# PaperPilot AI — Roadmap

This roadmap describes the direction of the project. It is intentionally
high-level; the authoritative, code-synced engineering detail lives in
**[CLAUDE.md](./CLAUDE.md)** (see §8 for feature status and §11 for the ordered
technical roadmap). The long-term product vision lives in `ProjectIdea.txt`.

Priorities and timelines may shift — this is a living document, and community
input via [issues](https://github.com/Rg9906/Research_Assistant/issues) and
[discussions](https://github.com/Rg9906/Research_Assistant/discussions) directly
shapes it. Nothing here has a hard date.

## Guiding principle

> The LLM is one component in a system; intelligence comes from planning,
> retrieval, memory, reasoning, tools, orchestration, and evaluation — not from
> prompting a model harder.

Everything below is in service of that.

## ✅ Done

- **Paper discovery + weighted ranking** — arXiv + Semantic Scholar, dedupe and
  merge, weighted scoring (similarity + citations + recency + PDF availability).
- **PDF availability preference** — ranking prefers papers that can actually be
  downloaded and chatted with, and recovers arXiv links for records that only
  had a publisher landing page.
- **PDF download + validation** — scheme allowlist, size caps, permanent-vs-
  transient failure handling.
- **Single-paper and multi-paper RAG chat** — LlamaIndex-backed, grounded,
  fanned out across every paper in a workspace and merged by score.
- **Tutor / Critic self-correction loop** — live in production; answers carry
  citations and an audit verdict.
- **Multi-level summarization** — the ten summary views, generated through the
  grounded path and cached per paper+level.
- **Structured citations** in every answer; live agent-activity status in the UI.

## 🚧 In progress / next up

1. **Ops hardening** — background indexing for slow PDF processing (currently
   synchronous in the request), rate limiting, and authentication for any
   non-localhost deployment.
2. **Wire in the Planner agent** — the LangGraph Planner → Search → Tutor →
   Critic pipeline is built and tested but not yet driven by any endpoint.
   Decomposing a user goal into subtasks is the last inert piece of the agent
   stack.
3. **Streaming responses** — `PaperSession.stream()` exists but no endpoint
   exposes it; a critic retry currently means a long silent wait.

## 🔭 Planned / future

- **Multi-paper comparison** — a Comparison agent over `retrieve_across_papers`.
- **Learning roadmaps** — generate a study path across a set of papers.
- **Quizzes** — auto-generated comprehension checks from indexed papers.
- **Long-term memory** — persist conversation and workspace memory across
  restarts (`WorkspaceChatStore` is currently process-local).
- **Additional search providers** — e.g. OpenAlex, Crossref, via the existing
  `SearchProvider` Protocol.

## How to influence the roadmap

- 👍 React to and comment on existing [issues](https://github.com/Rg9906/Research_Assistant/issues)
  to signal what matters to you.
- 💡 Open a *Feature request* issue for something not listed here.
- 🛠️ Pick up an item — comment on the issue first so we can avoid duplicate work.

See [CONTRIBUTING.md](./CONTRIBUTING.md) to get started.
