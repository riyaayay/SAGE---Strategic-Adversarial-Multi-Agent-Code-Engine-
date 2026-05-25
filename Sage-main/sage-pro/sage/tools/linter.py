import json
import structlog
from typing import List, Dict, Any
from sage.tools.sandbox import run_command_in_sandbox

logger = structlog.get_logger(__name__)

async def run_ruff(path: str) -> List[Dict[str, Any]]:
    """Invokes Ruff linter on a file path and returns findings.

    Args:
        path: Path to the python file.

    Returns:
        List of findings with rule, severity, line, and message.
    """
    cmd = ["ruff", "check", "--output-format=json", path]
    
    ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
    
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
        findings = []
        for issue in data:
            findings.append({
                "rule": issue.get("code"),
                "severity": "warning",
                "line": issue.get("location", {}).get("row"),
                "message": issue.get("message")
            })
        return findings
    except Exception as e:
        logger.error("ruff_parsing_failed", error=str(e))
        return []
