import faiss
import numpy as np
from typing import List, Tuple
from sage.core.aode import topological_route

class SageRouter:
    """FAISS HNSW + Gudhi Routing (Layer 2)."""
    def __init__(self, dimension: int = 1024):
        self.index = faiss.IndexHNSWFlat(dimension, 32)
        self.corpus = []

    def add_to_corpus(self, vectors: np.ndarray, texts: List[str]):
        self.index.add(vectors)
        self.corpus.extend(texts)

    def search_topological(self, query_vec: np.ndarray, k: int = 5) -> Tuple[List[str], Tuple[int, int]]:
        """
        Performs search and applies Persistent Homology to find 'voids'.
        """
        # 1. Broad retrieval via FAISS
        distances, indices = self.index.search(query_vec.reshape(1, -1), k * 4)
        candidate_indices = indices[0]
        
        # 2. Filter via AODE Topological Route
        candidate_vecs = np.array([self.index.reconstruct(int(i)) for i in candidate_indices])
        
        void_indices, bettis = topological_route(query_vec, candidate_vecs, k=k)
        
        # Map back to original indices
        final_indices = [candidate_indices[i] for i in void_indices]
        results = [self.corpus[i] for i in final_indices]
        
        return results, bettis
