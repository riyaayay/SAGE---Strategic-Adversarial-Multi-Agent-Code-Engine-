from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List

class BGEWrapper:
    """Wrapper for BGE-Large-En (Layer 1)."""
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.model = SentenceTransformer(model_name)
        
    def encode(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True)

    def encode_query(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True)
