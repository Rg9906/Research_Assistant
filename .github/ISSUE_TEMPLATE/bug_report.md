---
name: 🐛 Bug report
about: Report something that isn't working as expected
title: "[Bug]: "
labels: ["bug", "needs-triage"]
assignees: []
---

## Describe the bug

A clear and concise description of what the bug is.

## To reproduce

Steps to reproduce the behavior:

1. Go to '...'
2. Run '...' / click '...'
3. Enter query '...'
4. See error

## Expected behavior

What you expected to happen instead.

## Actual behavior

What actually happened. Include the full error message and stack trace if there
is one (from the terminal running the backend, or the browser console for
frontend issues).

```
<paste logs / traceback here>
```

## Which part is affected?

- [ ] Search / ranking (`src/paperpilot/search/`)
- [ ] PDF download / indexing (`src/paperpilot/document/`, `services/paper_chat/`)
- [ ] Chat / grounded QA (`services/grounded_qa.py`, `agent/`)
- [ ] Summarization
- [ ] FastAPI backend (`src/app/`)
- [ ] Frontend (`frontend/`)
- [ ] Other / not sure

## Environment

- **OS**: [e.g. Windows 11, macOS 14, Ubuntu 24.04]
- **Python version**: [e.g. 3.11.9] (`python --version`)
- **Node version** (if frontend): [e.g. 20.11.0] (`node --version`)
- **LLM provider configured**: [e.g. OpenAI / Gemini / Groq]
- **Commit / version**: [e.g. `main` @ abc1234] (`git rev-parse --short HEAD`)

## Additional context

Add any other context, screenshots, or a minimal reproduction here.

## Checklist

- [ ] I searched existing issues and this hasn't been reported already.
- [ ] I'm not reporting a **security vulnerability** (those go through
      [SECURITY.md](../SECURITY.md), not public issues).
- [ ] I have **not** pasted any API keys or secrets into this report.
