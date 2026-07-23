# Build a Quiz generator

## Background

ROADMAP.md lists "Quizzes — auto-generated comprehension checks from
indexed papers" under planned/future work; CLAUDE.md §8 marks it "Not
started." This is the third of the three vision features (alongside #022
Comparison and #023 Learning Roadmaps) named explicitly in ROADMAP.md's
"Planned / future" section.

## Why it matters

A quiz generated from a paper's actual retrieved content — grounded and
citation-backed the same way chat answers are — is a genuinely useful
comprehension-check feature for the "research assistant that helps you
actually learn a paper" pitch this project is built around, and it's a
comparatively contained scope compared to Comparison/Roadmap (single-paper,
not cross-paper).

## Proposed solution

Add a quiz-generation path (likely as a `SummarizerService`-adjacent
service, or a new summary-level-like construct) that:
1. Retrieves broadly across a single paper (similar to
   `SummarizerService`'s `apply_similarity_cutoff=False` pattern, since a
   good quiz needs coverage, not just the chunks nearest one query).
2. Generates a small set of question/answer pairs (multiple-choice or
   short-answer), each with a citation back to the specific chunk/page the
   question is drawn from — reusing `build_citations`/`nodes_to_chunks`.
3. Ideally routes generation through the grounded Tutor/Critic pattern (or
   a lighter-weight variant) so a "hallucinated" quiz question — one whose
   answer isn't actually supported by the paper — is caught the same way a
   hallucinated chat answer would be.
4. Exposed via a new endpoint (e.g.
   `POST /api/papers/{paper_id}/quiz`) and a new tab/view in
   `PaperSummary.tsx`, following the existing summary-tabs UI pattern.

## Acceptance criteria

- [ ] Given an indexed paper, produces a set of quiz questions with
      answers, each traceable to a citation.
- [ ] Questions are grounded in the paper's actual content — a rough audit
      pass (either a dedicated critic-style check or a spot-check test)
      should catch a question whose "correct" answer isn't supported by the
      cited chunk.
- [ ] Cached similarly to summaries (`SummarizerService`'s disk-cache
      pattern) so regenerating the same quiz doesn't cost a fresh LLM call
      every time.
- [ ] Covered by tests using the `StubChatModel` pattern.
- [ ] CLAUDE.md §8 updated.

## Suggested files

- `src/paperpilot/services/` (new module, likely sibling to
  `summarizer.py`)
- `src/app/api.py`, `src/app/utils.py`
- `frontend/src/components/PaperSummary.tsx`
- `tests/` (new test file)

## Difficulty

Hard

## Estimated time

3 days

## Labels

`feature`, `backend`, `frontend`, `enhancement`

## Dependencies

Recommended after #016 (Planner wiring), per roadmap ordering — not a hard
technical blocker.
