"""
Application configuration for PaperPilot AI.

Uses Pydantic Settings to provide typed, validated configuration that reads
from environment variables and .env files.

Why Pydantic Settings?
    Raw os.getenv() calls scattered throughout code create several problems:
    1. No type safety — everything is a string.
    2. No validation — missing or malformed values crash at runtime.
    3. No discoverability — you have to grep the codebase to find all config.
    4. No defaults management — default values are duplicated everywhere.

    Pydantic Settings solves all of these. It reads from .env files and
    environment variables, validates types, provides defaults, and gives
    you a single object you can import anywhere.

Usage:
    from paperpilot.config import get_settings

    settings = get_settings()
    print(settings.data_dir)
    print(settings.chunk_size)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with sensible defaults for local development.

    Values can be overridden via environment variables or a .env file.
    Environment variable names match the field names (case-insensitive).

    Attributes:
        project_name: Display name for the application.
        data_dir: Root directory for local data (downloaded PDFs, indexes).
        papers_dir: Subdirectory within data_dir for downloaded PDFs.

        chunk_size: Target size (in characters) for each text chunk.
                    500-1000 is typical for research papers. Larger chunks
                    preserve more context but dilute retrieval precision.
        chunk_overlap: Number of overlapping characters between consecutive
                       chunks. Overlap prevents information loss at chunk
                       boundaries. 10-20% of chunk_size is a good default.

        embedding_model_name: Name of the sentence-transformers model to use
                              for generating embeddings (used in Milestone 2).

        llm_provider: Which LLM backend to use (future configuration).
        openai_api_key: API key for OpenAI (loaded from .env, never hardcoded).
    """

    # -- Project --
    project_name: str = "PaperPilot AI"

    # -- Paths --
    data_dir: Path = Path("data")
    papers_dir: Path = Path("data/papers")
    index_dir: Path = Path("data/indexes")
    db_path: Path = Path("data/workspace.db")

    # -- Chunking --
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # -- Embedding --
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # -- Retrieval --
    retrieval_top_k: int = 5

    # -- LLM (Milestone 3+) --
    llm_provider: str = "openai"
    llm_model_name: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    openai_api_key: str = ""

    # -- Academic Search (Milestone 4+) --
    semantic_scholar_api_key: str = ""
    search_weight_similarity: float = 0.5
    search_weight_citations: float = 0.3
    search_weight_recency: float = 0.2
    search_decay_rate: float = 0.05

    model_config = {
        # Read from .env file in the project root
        "env_file": ".env",
        # Don't fail if .env file doesn't exist
        "env_file_encoding": "utf-8",
        # Allow extra fields from environment without crashing
        "extra": "ignore",
    }

    def ensure_directories(self) -> None:
        """Create required data directories if they don't exist.

        Called once at application startup. Keeps directory creation logic
        centralized rather than scattered across modules.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Why lru_cache?
        Settings should be loaded once and reused. Reading .env files and
        environment variables on every call would be wasteful. lru_cache
        ensures we create exactly one Settings instance for the lifetime
        of the process.

    Returns:
        The application Settings singleton.
    """
    return Settings()
