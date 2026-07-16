"""
FAISS vector store wrapper for similarity search.

This module provides a thin abstraction over FAISS (Facebook AI Similarity
Search) that handles the impedance mismatch between FAISS's low-level
integer-indexed API and our domain model with UUID-identified chunks.

How FAISS Works Internally (IndexFlatL2):
    FAISS stores vectors as a contiguous block of float32 values in memory.
    IndexFlatL2 is the simplest index type — it performs exact brute-force
    search by computing the L2 (Euclidean) distance between the query vector
    and every stored vector.

    For N vectors of dimension D:
    - Memory: N × D × 4 bytes (float32)
    - Search complexity: O(N × D) per query
    - Exact results (no approximation)

    For our use case (hundreds to low thousands of chunks per paper),
    brute-force is fast enough (~1ms for 1000 vectors). We would only need
    approximate indexes (IVF, HNSW) at 100K+ vectors.

Why Wrap FAISS?
    FAISS only knows about integer indices and float arrays. It has no
    concept of chunk IDs, paper metadata, or our domain model. This wrapper:
    1. Maps FAISS internal indices ↔ our chunk UUIDs
    2. Provides a clean search interface returning domain objects
    3. Handles persistence (save/load to disk)
    4. Isolates FAISS from the rest of the system — if we swap to ChromaDB
       or Pinecone later, only this file changes
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Raised when a vector store operation fails."""


class FAISSVectorStore:
    """A FAISS-backed vector store with chunk ID mapping.

    This class manages:
    1. A FAISS index that stores the actual embedding vectors
    2. A parallel list that maps FAISS integer positions to chunk UUIDs
    3. Save/load operations for persistence

    The separation between the FAISS index (which knows about vectors) and
    the ID mapping (which knows about our domain) is intentional. FAISS is
    a numerical search engine, not a database.

    Attributes:
        dimension: The dimensionality of stored vectors.
        count: Number of vectors currently stored.

    Usage:
        store = FAISSVectorStore(dimension=384)
        store.add(embeddings, chunk_ids)
        distances, ids = store.search(query_vector, k=5)
        store.save("data/indexes/my_index")
    """

    def __init__(self, dimension: int) -> None:
        """Create a new empty vector store.

        Args:
            dimension: The dimensionality of vectors that will be stored.
                       Must match the embedding model's output dimension
                       (e.g., 384 for all-MiniLM-L6-v2).
        """
        self.dimension = dimension

        # IndexFlatL2: exact brute-force search using L2 distance.
        # "Flat" means vectors are stored as-is (no compression/quantization).
        # "L2" means Euclidean distance is used for similarity.
        self._index = faiss.IndexFlatL2(dimension)

        # Maps FAISS internal position (0, 1, 2, ...) to our chunk UUID.
        # This list MUST stay in sync with the FAISS index.
        self._id_map: list[str] = []

        logger.info("Created FAISS vector store (dimension=%d)", dimension)

    @property
    def count(self) -> int:
        """Number of vectors currently in the store."""
        return self._index.ntotal

    def add(
        self,
        embeddings: np.ndarray,
        chunk_ids: list[UUID],
    ) -> None:
        """Add embeddings to the vector store with associated chunk IDs.

        Each embedding is associated with a chunk UUID. The mapping is
        maintained in a parallel list that mirrors the FAISS index order.

        Args:
            embeddings: Array of shape (n, dimension) containing the vectors.
            chunk_ids: List of n chunk UUIDs, one per embedding.

        Raises:
            ValueError: If embeddings shape doesn't match dimension, or if
                        the number of embeddings doesn't match chunk_ids.
        """
        if embeddings.ndim != 2:
            raise ValueError(
                f"Expected 2D embeddings array, got shape {embeddings.shape}"
            )

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, "
                f"got {embeddings.shape[1]}"
            )

        if embeddings.shape[0] != len(chunk_ids):
            raise ValueError(
                f"Number of embeddings ({embeddings.shape[0]}) doesn't match "
                f"number of chunk_ids ({len(chunk_ids)})"
            )

        # FAISS requires float32 contiguous arrays
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        # Add to FAISS index
        self._index.add(embeddings)

        # Maintain our ID mapping in parallel
        self._id_map.extend(str(cid) for cid in chunk_ids)

        logger.info(
            "Added %d vectors to store (total: %d)",
            len(chunk_ids),
            self.count,
        )

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 5,
    ) -> list[tuple[str, float]]:
        """Find the k most similar vectors to the query.

        Returns chunk IDs and their L2 distances to the query vector.
        Results are sorted by distance (most similar first).

        For L2 distance with normalized vectors:
        - Distance 0.0 = identical
        - Distance ~0.5 = somewhat similar
        - Distance ~1.0 = quite different
        - Distance ~2.0 = maximally different (opposite directions)

        Args:
            query_vector: A 1D array of shape (dimension,) or 2D of shape
                          (1, dimension).
            k: Number of results to return. Clamped to the number of stored
               vectors if k exceeds the store size.

        Returns:
            A list of (chunk_id_str, distance) tuples, sorted by distance
            ascending (most similar first).

        Raises:
            VectorStoreError: If the store is empty.
        """
        if self.count == 0:
            raise VectorStoreError("Cannot search an empty vector store")

        # Clamp k to the number of stored vectors
        k = min(k, self.count)

        # FAISS expects a 2D query array of shape (n_queries, dimension)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        query_vector = np.ascontiguousarray(query_vector, dtype=np.float32)

        # FAISS search returns:
        #   distances: array of shape (n_queries, k) — L2 distances
        #   indices:   array of shape (n_queries, k) — internal FAISS indices
        distances, indices = self._index.search(query_vector, k)

        # Convert FAISS results to our domain format
        results: list[tuple[str, float]] = []

        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                # FAISS returns -1 for unfilled slots (when k > ntotal)
                continue
            chunk_id_str = self._id_map[idx]
            results.append((chunk_id_str, float(dist)))

        return results

    def save(self, directory: Path | str) -> None:
        """Persist the vector store to disk.

        Saves two files:
        1. `index.faiss` — the FAISS index binary
        2. `id_map.json` — the chunk ID mapping

        Both files must stay in sync. Loading one without the other will
        produce incorrect results.

        Args:
            directory: Directory to save the files into. Created if it
                       doesn't exist.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        index_path = directory / "index.faiss"
        id_map_path = directory / "id_map.json"

        # Save FAISS index
        faiss.write_index(self._index, str(index_path))

        # Save ID mapping as JSON
        id_map_path.write_text(
            json.dumps(self._id_map, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Saved vector store to %s (%d vectors)", directory, self.count
        )

    @classmethod
    def load(cls, directory: Path | str) -> FAISSVectorStore:
        """Load a previously saved vector store from disk.

        Args:
            directory: Directory containing `index.faiss` and `id_map.json`.

        Returns:
            A fully restored FAISSVectorStore instance.

        Raises:
            FileNotFoundError: If the directory or required files don't exist.
        """
        directory = Path(directory)
        index_path = directory / "index.faiss"
        id_map_path = directory / "id_map.json"

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        if not id_map_path.exists():
            raise FileNotFoundError(f"ID map not found: {id_map_path}")

        # Load FAISS index
        index = faiss.read_index(str(index_path))

        # Load ID mapping
        id_map = json.loads(id_map_path.read_text(encoding="utf-8"))

        # Verify consistency
        if index.ntotal != len(id_map):
            raise VectorStoreError(
                f"Index/ID map mismatch: index has {index.ntotal} vectors, "
                f"ID map has {len(id_map)} entries"
            )

        # Reconstruct the store
        store = cls(dimension=index.d)
        store._index = index
        store._id_map = id_map

        logger.info(
            "Loaded vector store from %s (%d vectors)", directory, store.count
        )

        return store
