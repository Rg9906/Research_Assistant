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

# Anchor the .env lookup to the repository root rather than the process CWD.
# `env_file=".env"` is resolved relative to wherever the process was started,
# and the documented way to run the API is `uvicorn app.api:app` from inside
# src/ — so a repo-root .env was silently ignored and any key set only there
# (not also exported into the environment) looked unconfigured. A CWD-local
# .env still wins, since pydantic-settings gives precedence to the last file.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


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
    # `llm_provider` names the preferred backend ("openai", "gemini"/"google",
    # or "groq"). It is a preference, not a hard requirement: paperpilot.llm
    # tries it first and then falls back to any other provider that has an API
    # key, so a missing key degrades chat to a working provider instead of
    # taking the app down. Per-provider model ids live alongside their keys;
    # OpenAI keeps its two historical settings (llm_model_name for the agents,
    # rag_llm_model below for the RAG engine).
    llm_provider: str = "openai"
    llm_model_name: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # -- LlamaIndex & RAG Document Intelligence Settings --
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    # The paper's opening chunks (title/abstract/intro) are always included in
    # retrieved context, on top of the similarity hits. Vector search cannot
    # find them for document-level questions — "what problem does this paper
    # address?" shares no vocabulary with a problem statement — so without this
    # such questions get refused. 2 chunks ≈ the abstract plus the start of the
    # introduction. Set to 0 to disable (pure similarity retrieval).
    rag_lead_chunks: int = 2
    # 6, not 3: three 512-token chunks is often too little for a broad question
    # ("what problem does this paper address?") to be answerable, and the Tutor
    # is instructed to refuse rather than guess — so a too-small budget shows up
    # as spurious refusals, not as vague answers.
    rag_top_k: int = 6
    # Calibrated against bge-small-en-v1.5 cosine scores on real papers, not
    # guessed. Measured on "Attention Is All You Need":
    #   genuinely relevant questions -> top chunks score 0.65 - 0.77
    #   off-topic questions          -> top chunks score 0.48 - 0.57
    # The old default of 0.7 sat *inside* the relevant band, so ordinary
    # questions ("What problem does this paper address?", "Explain the
    # methodology") retrieved zero chunks and were wrongly refused. 0.60 lands
    # in the empty gap: it keeps relevant chunks and still rejects off-topic
    # ones. Re-measure before changing rag_embedding_model — these numbers are
    # a property of that model, not a universal constant.
    rag_similarity_threshold: float = 0.60
    rag_embedding_model: str = "BAAI/bge-small-en-v1.5"
    rag_llm_model: str = "gpt-4o-mini"
    # Grounded QA (services/grounded_qa.py): route chat through the
    # Tutor/Critic contract instead of LlamaIndex's default chat prompts.
    # Disable to fall back to the plain LlamaIndex chat path.
    # Summaries need broad document coverage, not the few chunks nearest one
    # query, so they retrieve more widely than chat (and with the similarity
    # cutoff disabled — see services/summarizer.py).
    # 6 rather than 10: the critic re-sends the whole context to audit the
    # answer, so each summary costs roughly double its chunk budget in tokens.
    # 10 chunks overran a Groq free-tier 6000 TPM limit in live testing.
    rag_summary_top_k: int = 6
    # Background summary prefetching (services/summarizer.py): when a paper page
    # opens, all remaining summary levels are generated ahead of the user
    # clicking their tabs, so switching tabs feels instant. Concurrency is
    # deliberately bounded — each level is a full grounded answer (tutor + critic
    # over the paper's context), so firing all ten at once would blow the LLM
    # provider's per-minute token quota (see the token-budgeting note above).
    # 2 workers ≈ the parallelism a free-tier quota sustains without constant
    # 429s; raise it if your provider quota is higher. Set enabled=false to fall
    # back to the old click-to-generate behaviour.
    rag_prefetch_enabled: bool = True
    rag_prefetch_workers: int = 2
    rag_grounded_qa_enabled: bool = True
    rag_max_critique_retries: int = 2
    # Set false on small per-minute LLM quotas: the audit re-sends the whole
    # context, roughly doubling tokens per answer. Answers stay grounded (the
    # Tutor's contract is unchanged), they are just not independently checked.
    rag_critique_enabled: bool = True
    rag_rerank_enabled: bool = False
    rag_rerank_model: str = "BAAI/bge-reranker-base"
    rag_rerank_top_n: int = 3
    storage_papers_dir: Path = Path("storage/papers")

    # -- Academic Search (Milestone 4+) --
    semantic_scholar_api_key: str = ""
    # Semantic Scholar enforces a per-key quota (1 rps on the standard grant).
    # Requests are paced client-side to that rate rather than discovered via
    # 429s — see search/rate_limit.py. Raise only if your key's quota is higher.
    semantic_scholar_rate_limit_rps: float = 1.0
    # Backstop for when another process sharing the key pushes us over anyway.
    # Observed in practice: Semantic Scholar can 429 the very first request of a
    # session even when correctly paced, so a budget of 2 (1s + 2s) was enough
    # to lose an entire search. 3 buys 1s + 2s + 4s.
    semantic_scholar_max_retries: int = 3
    # Ranking weights. PaperRanker normalizes these to sum to 1.0 if they don't,
    # so the absolute values matter less than their ratios. Availability is
    # weighted meaningfully (0.25) but below similarity: an openable paper is
    # strongly preferred, yet a far-more-relevant one that happens to be
    # abstract-only can still surface rather than being buried. Raise
    # search_weight_availability toward similarity to make chattability nearly
    # decisive; lower it to treat the PDF as a tiebreaker.
    search_weight_similarity: float = 0.4
    search_weight_citations: float = 0.2
    search_weight_recency: float = 0.15
    search_weight_availability: float = 0.25
    search_decay_rate: float = 0.05

    model_config = {
        # Read the repo-root .env, then any .env in the current working
        # directory (which takes precedence). See _REPO_ROOT_ENV above.
        "env_file": (str(_REPO_ROOT_ENV), ".env"),
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
