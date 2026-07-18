"""LlamaIndex vector index creation, IngestionPipeline, and storage persistence."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Document,
    Settings as LlamaSettings,
)
from llama_index.core.node_parser import SentenceSplitter

from paperpilot.config import get_settings

logger = logging.getLogger(__name__)


def configure_llama_defaults() -> None:
    """Configure global LlamaIndex LLM and Embedding defaults based on environment settings."""
    settings = get_settings()
    api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key

    # Embeddings: HuggingFace local embedding model
    try:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        LlamaSettings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("Configured LlamaIndex HuggingFaceEmbedding (BAAI/bge-small-en-v1.5)")
    except Exception as e:
        logger.warning("Could not initialize HuggingFaceEmbedding: %s. Using default embed_model.", e)

    # LLM: OpenAI or Mock
    if api_key:
        try:
            from llama_index.llms.openai import OpenAI
            LlamaSettings.llm = OpenAI(
                model=settings.llm_model_name,
                temperature=settings.llm_temperature,
                api_key=api_key,
            )
            logger.info("Configured LlamaIndex OpenAI LLM (%s)", settings.llm_model_name)
        except Exception as e:
            logger.warning("Could not initialize LlamaIndex OpenAI LLM: %s", e)


class PaperIndexingService:
    """Manages LlamaIndex transformations, index construction, and persistence."""

    def __init__(self) -> None:
        configure_llama_defaults()

    def build_and_persist_index(
        self, documents: List[Document], storage_dir: Path
    ) -> VectorStoreIndex:
        """Create a VectorStoreIndex using SentenceSplitter and persist it to disk."""
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)

        index = VectorStoreIndex.from_documents(
            documents,
            transformations=[splitter],
        )

        storage_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(storage_dir))
        logger.info("Successfully built and persisted LlamaIndex to %s", storage_dir)
        return index

    def load_index(self, storage_dir: Path) -> VectorStoreIndex:
        """Load an existing LlamaIndex from disk storage."""
        storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(storage_context)
        logger.info("Successfully loaded LlamaIndex from %s", storage_dir)
        return index
