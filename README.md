# PaperPilot AI

An autonomous multi-agent research assistant for discovering, understanding, and learning research papers.

## Overview

PaperPilot AI goes beyond "Chat with PDF" — it's designed to act like a graduate research assistant that discovers relevant literature, ranks papers by importance, processes them into searchable knowledge, teaches concepts at multiple difficulty levels, and remembers your research journey.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Install in development mode
pip install -e ".[dev]"

# 4. Copy environment template and fill in your keys
copy .env.example .env

# 5. Run tests
pytest
```

## Project Structure

```
src/paperpilot/
├── core/           # Data models and shared types
├── document/       # PDF extraction and chunking
└── config.py       # Application configuration
```

## Current Status

**Milestone 1** — Foundation: Core data models + PDF processing pipeline.
