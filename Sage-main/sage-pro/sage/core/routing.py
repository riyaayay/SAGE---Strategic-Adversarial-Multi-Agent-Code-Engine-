"""
SAGE-PRO Topological Void Router
═════════════════════════════════
Identifies persistent voids (H_k ≠ 0) in the codebase embedding space
and routes tasks to the FARTHEST domain — maximum divergence.

Uses SentenceTransformers for semantic embedding, FAISS HNSW for indexing,
and Gudhi Persistent Homology for void detection.

Key AODE property:
    Target = argmax_i D(Q, A_i)   # farthest domain = maximum divergence
"""

import faiss
import numpy as np
import structlog
from typing import List, Tuple

from sentence_transformers import SentenceTransformer
from sage.core.aode import persistent_homology_features

logger = structlog.get_logger(__name__)


class CodeTopologyRouter:
    """Identifies 'topological voids' in the codebase to route tasks to underserved logic.

    Uses SentenceTransformers for semantic embedding and FAISS HNSW for
    high-speed neighbor discovery, followed by Persistent Homology feature
    extraction to find structural gaps.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        index_dims: int = 384,
        max_neighbors: int = 5,
        search_cap: int = 500,
    ) -> None:
        """Initializes the router with the specified embedder and index.

        Args:
            model_name: The SentenceTransformer model to use for embedding.
            index_dims: Dimensionality of the embedding vectors.
            max_neighbors: Max topological voids to return.
            search_cap: Max index size to scan.
        """
        self.embedder = SentenceTransformer(model_name)
        self.index = faiss.IndexHNSWFlat(index_dims, 32)
        self.index_dims = index_dims
        self.max_neighbors = max_neighbors
        self.search_cap = search_cap
        self.file_map: List[str] = []
        logger.info("topology_router_initialized", model=model_name)

    def index_repository(self, repo_files: List[Tuple[str, str]]) -> None:
        """Embeds and indexes all files in the repository.

        Args:
            repo_files: List of (filename, content) tuples.
        """
        if not repo_files:
            return

        contents = [content for _, content in repo_files]
        embeddings = self.embedder.encode(contents, convert_to_numpy=True)

        self.index.add(embeddings)
        self.file_map = [name for name, _ in repo_files]
        logger.info("repository_indexed", file_count=len(repo_files))

    def route(
        self,
        task: str,
        repo_files: List[Tuple[str, str]],
    ) -> List[Tuple[str, Tuple[int, int], float]]:
        """Routes the task to relevant files based on topological void proximity.

        AODE principle: we find the FARTHEST files (argmax distance), not the
        nearest.  This ensures the engine explores topological voids — the
        regions of concept-space that are maximally underserved by the existing
        codebase.

        Args:
            task: The natural language task description.
            repo_files: Repository file data (needed if not yet indexed).

        Returns:
            A list of (filename, (start_line, end_line), novelty_score)
            ranked by MAXIMUM divergence (farthest first).
        """
        if self.index.ntotal == 0:
            self.index_repository(repo_files)

        if self.index.ntotal == 0:
            logger.warning("route_empty_index")
            return []

        task_vec = self.embedder.encode([task], convert_to_numpy=True)

        # ── ARGMAX DISTANCE: search ALL indexed vectors, pick the FARTHEST ──
        # Cap at search_cap to avoid OOM on very large repos
        search_k = min(self.index.ntotal, self.search_cap)
        distances, indices = self.index.search(task_vec, search_k)

        # distances from HNSW are L2 — higher = farther = more novel
        # Sort by DESCENDING distance to get farthest-first
        sorted_order = np.argsort(distances[0])[::-1]  # descending
        k = min(self.max_neighbors, len(sorted_order))
        farthest_indices = [indices[0][sorted_order[i]] for i in range(k)]
        farthest_distances = [distances[0][sorted_order[i]] for i in range(k)]

        # ── REAL EMBEDDINGS for Persistent Homology (not random noise) ──
        neighborhood_vecs = []
        for idx in farthest_indices:
            if idx != -1:
                real_vec = self.index.reconstruct(int(idx))
                neighborhood_vecs.append(real_vec.reshape(1, -1))

        if not neighborhood_vecs:
            logger.warning("route_no_valid_neighbors")
            return []

        # Compute PH features on real embeddings
        ph_features = persistent_homology_features(np.vstack(neighborhood_vecs))
        novelty_score = float(ph_features["b1"] + ph_features["b2"]) / 10.0

        logger.info(
            "void_topology_computed",
            b0=ph_features["b0"],
            b1=ph_features["b1"],
            b2=ph_features["b2"],
            novelty_score=novelty_score,
        )

        # ── Build results: distance IS the score (higher = more divergent) ──
        results = []
        for i, idx in enumerate(farthest_indices):
            if idx != -1 and idx < len(self.file_map):
                results.append((
                    self.file_map[idx],
                    (1, 100),  # line range (refined by downstream tools)
                    float(farthest_distances[i]) + novelty_score,
                ))

        # Already sorted farthest-first, but ensure consistency
        return sorted(results, key=lambda x: x[2], reverse=True)
