"""
SAGE-PRO Tool: Browser Fetch
═════════════════════════════
Fetches and extracts content from a specific URL.
Uses httpx for simple pages, BeautifulSoup for parsing.

Config: TOOL_FETCH_TIMEOUT (env var, default 15s)
"""

import os
import structlog
from typing import Dict, Any, List, Union

logger = structlog.get_logger(__name__)

FETCH_TIMEOUT = int(os.environ.get("TOOL_FETCH_TIMEOUT", "15"))
MAX_CONTENT_LENGTH = int(os.environ.get("TOOL_FETCH_MAX_CONTENT", "8000"))


async def tool_browser_fetch(
    url: str,
    extract: str,
    reason: str = "",
) -> Dict[str, Any]:
    """Fetches content from a URL and extracts specified elements.

    Args:
        url: The URL to fetch.
        extract: What to extract — full_text, code_blocks, api_endpoints, etc.
        reason: Why this fetch is necessary.

    Returns:
        Dict with 'url', 'content', 'extract', 'reason'.
    """
    import httpx

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4_not_installed")
        return {
            "url": url,
            "content": "",
            "extract": extract,
            "error": "beautifulsoup4 not installed",
        }

    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            r = await client.get(url, follow_redirects=True)
            r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        if extract == "code_blocks":
            blocks = [c.get_text() for c in soup.find_all(["code", "pre"])]
            content: Union[str, List[str]] = blocks[:20]  # cap at 20 blocks
        elif extract == "api_endpoints":
            # Look for common API doc patterns
            endpoints = []
            for tag in soup.find_all(["code", "span", "td"]):
                text = tag.get_text().strip()
                if text.startswith(("/", "GET ", "POST ", "PUT ", "DELETE ", "PATCH ")):
                    endpoints.append(text)
            content = list(set(endpoints))[:30]
        elif extract == "css_variables":
            styles = soup.find_all("style")
            css_vars = []
            for s in styles:
                text = s.get_text()
                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith("--"):
                        css_vars.append(line)
            content = css_vars[:50]
        elif extract == "schema":
            # Extract JSON-LD or structured data
            scripts = soup.find_all("script", {"type": "application/ld+json"})
            content = [s.get_text() for s in scripts][:5]
        else:
            # full_text or component_list — just get text
            content = soup.get_text(separator="\n", strip=True)[:MAX_CONTENT_LENGTH]

        logger.info("browser_fetch_complete", url=url[:80], extract=extract)
        return {"url": url, "content": content, "extract": extract, "reason": reason}

    except Exception as e:
        logger.error("browser_fetch_failed", url=url[:80], error=str(e))
        return {"url": url, "content": "", "extract": extract, "error": str(e)}
