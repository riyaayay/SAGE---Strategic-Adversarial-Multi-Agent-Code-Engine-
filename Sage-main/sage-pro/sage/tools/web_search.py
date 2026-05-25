"""
SAGE-PRO Tool: Web Search
══════════════════════════
DuckDuckGo-based web search with intent filtering.
Prioritises official docs, GitHub, PyPI, npm over forums.

Config: None required — uses free DuckDuckGo API.
"""

import os
import structlog
from typing import Dict, Any, List

logger = structlog.get_logger(__name__)

# Max content length per result — soft-coded
MAX_RESULT_BODY_LENGTH = int(os.environ.get("TOOL_SEARCH_MAX_BODY", "500"))


async def tool_web_search(
    query: str,
    intent: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Searches the web using DuckDuckGo.

    Args:
        query: The search query string.
        intent: Why the search is happening (fetch_docs, verify_api, etc.).
        max_results: Number of results to return.

    Returns:
        Dict with 'results' list, 'query', and 'intent'.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo_search_not_installed")
        return {
            "results": [],
            "query": query,
            "intent": intent,
            "error": "duckduckgo-search package not installed",
        }

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        # Truncate body text to keep context window manageable
        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "body": r.get("body", "")[:MAX_RESULT_BODY_LENGTH],
            })

        logger.info(
            "web_search_complete",
            query=query[:80],
            intent=intent,
            count=len(results),
        )
        return {"results": results, "query": query, "intent": intent}

    except Exception as e:
        logger.error("web_search_failed", error=str(e))
        return {"results": [], "query": query, "intent": intent, "error": str(e)}
