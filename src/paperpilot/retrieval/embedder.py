"""
Embedding generation using Sentence Transformers.

This module converts text into dense vector representations (embeddings) that
capture semantic meaning. These embeddings are the foundation of similarity
search — text with similar meanings produces similar vectors.

How Sentence Transformers Work (High-Level):
    1. The input text is tokenized (split into subword tokens).
    2. Tokens are passed through a transformer encoder (e.g., MiniLM, a
       distilled version of BERT).
    3. The encoder produces a contextual embedding for each token.
    4. A pooling layer (typically mean pooling) aggregates token embeddings
       into a single fixed-size vector representing the entire input text.
    5. The result is a dense float vector (e.g., 384 dimensions for MiniLM).

    The model was trained using contrastive learning: given pairs of similar
    and dissimilar sentences, it learned to place similar sentences close
    together in vector space and dissimilar ones far apart.

Why `all-MiniLM-L6-v2`?
    - 384 dimensions, 22M parameters, ~90MB model size
    - Trained on 1B+ sentence pairs
    - Good balance of quality vs. speed vs. size
    - Runs comfortably on CPU (no GPU required)
    - Embeds ~2800 sentences/second on a modern CPU
    - Alternative: `all-mpnet-base-v2` (768 dims, better quality, 2x slower)
"""

from __future__ import annotations

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Generates text embeddings using a Sentence Transformers model.

    This class wraps a SentenceTransformer model and provides a clean
    interface for embedding text. The model is loaded once on initialization
    and reused for all subsequent calls.

    Why a class instead of functions?
        Model loading is expensive (~1-2 seconds, ~90MB in memory). We load
        once and reuse. A class naturally encapsulates this stateful behavior.
        Functions would need to accept the model as a parameter or use globals.

    Attributes:
        model_name: Name of the sentence-transformers model being used.
        embedding_dim: Dimensionality of the output embeddings.

    Usage:
        engine = EmbeddingEngine()
        vectors = engine.embed_texts(["Hello world", "Foo bar"])
        query_vec = engine.embed_query("What is attention?")
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the embedding engine by loading the model.

        Args:
            model_name: A model identifier from the Sentence Transformers
                        model hub (https://www.sbert.net/docs/pretrained_models.html).
                        The model is downloaded on first use and cached locally
                        (~/.cache/torch/sentence_transformers/).
        """
        self.model_name = model_name
        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self.embedding_dim: int = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Model loaded: %s (dimension=%d)", model_name, self.embedding_dim
        )

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts into dense vectors.

        Batching is important for performance: the model processes multiple
        texts in parallel using matrix operations. Embedding 100 texts at
        once is much faster than embedding them one by one.

        Args:
            texts: List of text strings to embed.

        Returns:
            A numpy array of shape (len(texts), embedding_dim), where each
            row is the L2-normalized embedding of the corresponding text.

        Raises:
            ValueError: If texts is empty.
        """
        if not texts:
            raise ValueError("Cannot embed an empty list of texts")

        logger.debug("Embedding %d texts", len(texts))

        # encode() handles tokenization, forward pass, and pooling internally.
        # normalize_embeddings=True applies L2 normalization, which ensures:
        #   1. All vectors have unit length (magnitude = 1)
        #   2. L2 distance and cosine similarity give equivalent rankings
        #   3. Similarity scores are more interpretable
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        # Ensure we return a proper 2D numpy array of float32
        embeddings = np.asarray(embeddings, dtype=np.float32)

        logger.debug("Produced embeddings of shape %s", embeddings.shape)
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string into a dense vector.

        This is a convenience method for the common case of embedding one
        query for similarity search. It returns a 1D vector (not 2D).

        Args:
            query: The query text to embed.

        Returns:
            A 1D numpy array of shape (embedding_dim,).
        """
        if not query.strip():
            raise ValueError("Cannot embed an empty query")

        # embed_texts returns (1, dim), we squeeze to (dim,) for convenience
        embedding = self.embed_texts([query])
        return embedding[0]
