"""
Tests for the embedding engine.

These tests verify that the Sentence Transformers wrapper produces
correctly shaped, normalized embeddings and that semantically similar
texts produce similar vectors.

Note: The first run will download the model (~90MB). Subsequent runs
use the cached model.
"""

import numpy as np
import pytest

from paperpilot.retrieval.embedder import EmbeddingEngine


# Use a module-scoped fixture so the model is loaded only once per test session.
# Model loading takes ~1-2 seconds — we don't want to pay that per test.
@pytest.fixture(scope="module")
def engine() -> EmbeddingEngine:
    """Load the embedding model once for all tests in this module."""
    return EmbeddingEngine(model_name="all-MiniLM-L6-v2")


class TestEmbeddingEngine:
    """Tests for the EmbeddingEngine class."""

    def test_embedding_shape(self, engine: EmbeddingEngine):
        """Embeddings should have shape (n_texts, embedding_dim)."""
        texts = ["Hello world", "Foo bar baz"]
        embeddings = engine.embed_texts(texts)

        assert embeddings.shape == (2, engine.embedding_dim)
        assert engine.embedding_dim == 384  # MiniLM-L6-v2

    def test_embedding_dtype(self, engine: EmbeddingEngine):
        """Embeddings should be float32 (FAISS requirement)."""
        embeddings = engine.embed_texts(["test"])
        assert embeddings.dtype == np.float32

    def test_embeddings_are_normalized(self, engine: EmbeddingEngine):
        """All embedding vectors should have unit L2 norm (~1.0).

        L2 normalization ensures that cosine similarity and L2 distance
        give equivalent rankings, and that similarity scores are bounded.
        """
        texts = ["The transformer model", "Attention mechanism", "Neural networks"]
        embeddings = engine.embed_texts(texts)

        # Compute L2 norms — should all be ~1.0
        norms = np.linalg.norm(embeddings, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_similar_texts_produce_similar_embeddings(self, engine: EmbeddingEngine):
        """Semantically similar texts should have small L2 distance."""
        similar_a = "The transformer architecture uses self-attention"
        similar_b = "Self-attention is the core mechanism of transformers"
        different = "I enjoy eating pizza on Fridays"

        emb_a, emb_b, emb_diff = engine.embed_texts([similar_a, similar_b, different])

        # L2 distance between similar texts
        dist_similar = np.linalg.norm(emb_a - emb_b)
        # L2 distance between dissimilar texts
        dist_different = np.linalg.norm(emb_a - emb_diff)

        # Similar texts should be closer than dissimilar texts
        assert dist_similar < dist_different, (
            f"Similar distance ({dist_similar:.4f}) should be less than "
            f"different distance ({dist_different:.4f})"
        )

    def test_embed_query_returns_1d(self, engine: EmbeddingEngine):
        """embed_query should return a 1D vector, not a 2D array."""
        vec = engine.embed_query("What is attention?")
        assert vec.ndim == 1
        assert vec.shape == (engine.embedding_dim,)

    def test_embed_query_matches_embed_texts(self, engine: EmbeddingEngine):
        """embed_query and embed_texts should produce identical vectors."""
        text = "How does the transformer work?"
        vec_query = engine.embed_query(text)
        vec_batch = engine.embed_texts([text])[0]

        np.testing.assert_allclose(vec_query, vec_batch, atol=1e-6)

    def test_empty_list_raises_error(self, engine: EmbeddingEngine):
        """Embedding an empty list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            engine.embed_texts([])

    def test_empty_query_raises_error(self, engine: EmbeddingEngine):
        """Embedding an empty query should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            engine.embed_query("   ")

    def test_deterministic_output(self, engine: EmbeddingEngine):
        """Same input should always produce the same embedding."""
        text = "Reproducibility matters"
        vec1 = engine.embed_query(text)
        vec2 = engine.embed_query(text)
        np.testing.assert_array_equal(vec1, vec2)
