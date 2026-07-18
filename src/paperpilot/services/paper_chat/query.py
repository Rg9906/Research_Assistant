"""Retrieval and Chat Engine abstractions using native LlamaIndex mechanisms."""

from __future__ import annotations

import logging
from llama_index.core import VectorStoreIndex
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core.query_engine import BaseQueryEngine

logger = logging.getLogger(__name__)


class PaperQueryService:
    """Factory for creating LlamaIndex ChatEngine and QueryEngine abstractions."""

    @staticmethod
    def create_chat_engine(index: VectorStoreIndex) -> BaseChatEngine:
        """Create a native LlamaIndex ChatEngine with grounded retrieval context."""
        return index.as_chat_engine(
            chat_mode="condense_plus_context",
            similarity_top_k=3,
        )

    @staticmethod
    def create_query_engine(index: VectorStoreIndex) -> BaseQueryEngine:
        """Create a native LlamaIndex QueryEngine for single-shot retrieval QA."""
        return index.as_query_engine(
            similarity_top_k=3,
        )
