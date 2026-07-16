"""
Tests for the FAISS vector store wrapper.

These tests verify the add/search/save/load operations and the
chunk ID mapping that bridges FAISS indices to our domain model.
"""

from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from paperpilot.retrieval.vector_store import FAISSVectorStore, VectorStoreError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_embeddings(n: int, dim: int = 384) -> np.ndarray:
    """Generate random normalized embeddings for testing."""
    rng = np.random.default_rng(seed=42)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    # L2 normalize
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


def _random_ids(n: int) -> list:
    """Generate n random UUIDs."""
    return [uuid4() for _ in range(n)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFAISSVectorStore:
    """Tests for the FAISSVectorStore class."""

    def test_empty_store(self):
        """A new store should have 0 vectors."""
        store = FAISSVectorStore(dimension=384)
        assert store.count == 0
        assert store.dimension == 384

    def test_add_and_count(self):
        """Adding vectors should increase the count."""
        store = FAISSVectorStore(dimension=384)
        embeddings = _random_embeddings(5)
        ids = _random_ids(5)

        store.add(embeddings, ids)
        assert store.count == 5

    def test_add_multiple_batches(self):
        """Adding multiple batches should accumulate."""
        store = FAISSVectorStore(dimension=384)

        store.add(_random_embeddings(3), _random_ids(3))
        store.add(_random_embeddings(2), _random_ids(2))

        assert store.count == 5

    def test_search_returns_correct_count(self):
        """Search should return exactly k results (or fewer if store is smaller)."""
        store = FAISSVectorStore(dimension=384)
        store.add(_random_embeddings(10), _random_ids(10))

        query = _random_embeddings(1)[0]
        results = store.search(query, k=5)

        assert len(results) == 5

    def test_search_clamps_k(self):
        """If k > store size, return all vectors."""
        store = FAISSVectorStore(dimension=384)
        store.add(_random_embeddings(3), _random_ids(3))

        query = _random_embeddings(1)[0]
        results = store.search(query, k=10)

        assert len(results) == 3

    def test_search_returns_correct_ids(self):
        """Search results should contain valid chunk ID strings."""
        store = FAISSVectorStore(dimension=384)
        ids = _random_ids(5)
        store.add(_random_embeddings(5), ids)

        query = _random_embeddings(1)[0]
        results = store.search(query, k=3)

        id_strs = {str(uid) for uid in ids}
        for chunk_id_str, distance in results:
            assert chunk_id_str in id_strs

    def test_search_ordered_by_distance(self):
        """Results should be sorted by distance (ascending)."""
        store = FAISSVectorStore(dimension=384)
        store.add(_random_embeddings(20), _random_ids(20))

        query = _random_embeddings(1)[0]
        results = store.search(query, k=10)

        distances = [dist for _, dist in results]
        assert distances == sorted(distances), "Results should be sorted by distance"

    def test_identical_vector_has_zero_distance(self):
        """Searching for an exact match should return distance ~0."""
        store = FAISSVectorStore(dimension=384)
        embeddings = _random_embeddings(5)
        ids = _random_ids(5)
        store.add(embeddings, ids)

        # Search for the first embedding itself
        results = store.search(embeddings[0], k=1)

        assert len(results) == 1
        chunk_id_str, distance = results[0]
        assert chunk_id_str == str(ids[0])
        assert distance < 1e-5, f"Expected ~0 distance, got {distance}"

    def test_search_empty_store_raises_error(self):
        """Searching an empty store should raise VectorStoreError."""
        store = FAISSVectorStore(dimension=384)
        query = _random_embeddings(1)[0]

        with pytest.raises(VectorStoreError, match="empty"):
            store.search(query, k=5)

    def test_dimension_mismatch_raises_error(self):
        """Adding embeddings with wrong dimension should raise ValueError."""
        store = FAISSVectorStore(dimension=384)
        wrong_dim = _random_embeddings(3, dim=128)

        with pytest.raises(ValueError, match="dimension mismatch"):
            store.add(wrong_dim, _random_ids(3))

    def test_count_mismatch_raises_error(self):
        """Mismatched embeddings/ids count should raise ValueError."""
        store = FAISSVectorStore(dimension=384)

        with pytest.raises(ValueError, match="doesn't match"):
            store.add(_random_embeddings(3), _random_ids(5))

    def test_save_and_load(self, tmp_path: Path):
        """A saved store should be loadable with identical state."""
        # Create and populate a store
        store = FAISSVectorStore(dimension=384)
        embeddings = _random_embeddings(10)
        ids = _random_ids(10)
        store.add(embeddings, ids)

        # Save
        save_dir = tmp_path / "test_index"
        store.save(save_dir)

        # Verify files exist
        assert (save_dir / "index.faiss").exists()
        assert (save_dir / "id_map.json").exists()

        # Load
        loaded = FAISSVectorStore.load(save_dir)

        assert loaded.count == store.count
        assert loaded.dimension == store.dimension

        # Search should produce identical results
        query = embeddings[0]
        original_results = store.search(query, k=5)
        loaded_results = loaded.search(query, k=5)

        assert len(original_results) == len(loaded_results)
        for (oid, odist), (lid, ldist) in zip(original_results, loaded_results):
            assert oid == lid
            assert abs(odist - ldist) < 1e-5

    def test_load_missing_dir_raises_error(self, tmp_path: Path):
        """Loading from a non-existent directory should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            FAISSVectorStore.load(tmp_path / "nonexistent")
