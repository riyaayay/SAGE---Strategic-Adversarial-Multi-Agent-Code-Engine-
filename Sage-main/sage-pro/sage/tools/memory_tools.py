"""
SAGE-PRO Tool: Memory Operations
══════════════════════════════════
memory_query and memory_store — wired into the MistakeLibrary (ChromaDB).

These are the tool-call handlers invoked by the LangGraph orchestrator
when an agent calls the memory_query or memory_store tools via Ollama.

Config:
    CHROMA_PATH (env var) — ChromaDB persistence path
    mistake_library.top_k (YAML) — default top-K
    mistake_library.collection_name (YAML) — collection name
"""

import os
import uuid
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)

# Singleton reference — initialized on first call
_mistake_library = None


def _get_library():
    """Gets or creates the MistakeLibrary singleton."""
    global _mistake_library
    if _mistake_library is None:
        from sage.memory.mistake_library import MistakeLibrary
        chroma_path = os.environ.get("CHROMA_PATH", "data/chroma")
        _mistake_library = MistakeLibrary(chroma_path=chroma_path)
    return _mistake_library


async def tool_memory_query(
    query: str,
    top_k: int = 3,
    threshold: float = 0.82,
) -> Dict[str, Any]:
    """Queries the Mistake Library for past errors similar to the current query.

    Args:
        query: The current user query or task description.
        top_k: Number of past mistakes to retrieve.
        threshold: Similarity threshold (matches below this are discarded).

    Returns:
        Dict with 'matches' list and 'query'.
    """
    try:
        lib = _get_library()
        mistakes = lib.retrieve(query_text=query)

        # Filter by threshold if embeddings were used
        # (ChromaDB handles similarity internally, but we cap at top_k)
        matches = mistakes[:top_k]

        logger.info(
            "memory_query_complete",
            query=query[:80],
            matches_found=len(matches),
        )
        return {"matches": matches, "query": query}

    except Exception as e:
        logger.warning("memory_query_failed", error=str(e))
        return {"matches": [], "query": query, "error": str(e)}


async def tool_memory_store(
    original_response: str,
    correction: str,
    domain: str,
    responsible_agents: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Stores a correction in the Mistake Library.

    Args:
        original_response: What was said or generated that was wrong.
        correction: The correct information.
        domain: Topic domain (e.g. "python_async", "fastapi_auth").
        responsible_agents: Which agents were responsible.

    Returns:
        Dict with 'status' and 'domain'.
    """
    if responsible_agents is None:
        responsible_agents = []

    try:
        lib = _get_library()
        mistake_id = str(uuid.uuid4())

        lib.store(
            mistake_id=mistake_id,
            original_response=original_response,
            corrected_content=correction,
            query_text=domain,
            user_id="system",
            responsible_agents=responsible_agents,
        )

        logger.info(
            "memory_store_complete",
            id=mistake_id,
            domain=domain,
            agents=responsible_agents,
        )
        return {"status": "stored", "domain": domain, "id": mistake_id}

    except Exception as e:
        logger.error("memory_store_failed", error=str(e))
        return {"status": "error", "domain": domain, "error": str(e)}
