"""
SAGE-PRO Mistake Library
═════════════════════════
ChromaDB-backed vector store of past errors.
Every confirmed correction is embedded and stored.
At inference time, the top-K most similar past mistakes are
retrieved and injected as hidden context.

Config: chroma_path from env var CHROMA_PATH.
"""

import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)


class MistakeLibrary:
    """ChromaDB vector store of past AI errors."""

    def __init__(
        self,
        chroma_path: str,
        collection_name: str = "mistake_library",
        top_k: int = 3,
    ) -> None:
        """Initializes the Mistake Library.

        Args:
            chroma_path: Filesystem path for ChromaDB persistence.
            collection_name: Name of the ChromaDB collection.
            top_k: Number of similar mistakes to retrieve at inference time.
        """
        import chromadb

        self.top_k = top_k
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "mistake_library_initialized",
            path=chroma_path,
            collection=collection_name,
            existing_count=self.collection.count(),
        )

    def store(
        self,
        mistake_id: str,
        original_response: str,
        corrected_content: str,
        query_text: str,
        user_id: str,
        responsible_agents: List[str],
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Stores a confirmed correction in the library.

        Args:
            mistake_id: UUID of the correction record.
            original_response: The AI's wrong response.
            corrected_content: What the user corrected it to.
            query_text: The original user query.
            user_id: ID of the user who made the correction.
            responsible_agents: List of agents responsible.
            embedding: Pre-computed embedding. If None, ChromaDB auto-embeds.
        """
        metadata = {
            "user_id": user_id,
            "responsible_agents": ",".join(responsible_agents),
            "original_response": original_response[:500],
        }

        kwargs = {
            "ids": [mistake_id],
            "documents": [f"WRONG: {original_response}\nCORRECTED: {corrected_content}"],
            "metadatas": [metadata],
        }

        if embedding is not None:
            kwargs["embeddings"] = [embedding]

        self.collection.upsert(**kwargs)
        logger.info("mistake_stored", id=mistake_id, agents=responsible_agents)

    def retrieve(
        self,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Retrieves the top-K most similar past mistakes.

        Args:
            query_text: The current user query.
            query_embedding: Pre-computed embedding. If None, ChromaDB auto-embeds.
            user_id: Optional user filter (retrieve user-specific mistakes first).

        Returns:
            List of dicts with 'original' and 'corrected' keys.
        """
        if self.collection.count() == 0:
            return []

        kwargs: Dict[str, Any] = {"n_results": self.top_k}

        if query_embedding is not None:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            kwargs["query_texts"] = [query_text]

        if user_id:
            kwargs["where"] = {"user_id": user_id}

        try:
            results = self.collection.query(**kwargs)
        except Exception as e:
            logger.warning("mistake_retrieval_failed", error=str(e))
            # Retry without user filter
            kwargs.pop("where", None)
            try:
                results = self.collection.query(**kwargs)
            except Exception:
                return []

        mistakes = []
        if results and results.get("documents"):
            for doc in results["documents"][0]:
                parts = doc.split("\nCORRECTED: ", 1)
                original = parts[0].replace("WRONG: ", "", 1) if parts else doc
                corrected = parts[1] if len(parts) > 1 else ""
                mistakes.append({"original": original, "corrected": corrected})

        logger.info("mistakes_retrieved", count=len(mistakes))
        return mistakes
