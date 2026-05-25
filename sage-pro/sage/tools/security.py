import json
import structlog
from typing import List, Dict, Any
from sage.tools.sandbox import run_command_in_sandbox

logger = structlog.get_logger(__name__)

async def run_bandit(path: str) -> List[Dict[str, Any]]:
    """Invokes Bandit security scanner and returns findings.

    Args:
        path: The filesystem path to scan.

    Returns:
        A list of dictionaries containing Bandit findings (HIGH/MEDIUM severity).
    """
    cmd = ["bandit", "-f", "json", "-r", path]
    
    ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
    
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
        findings = []
        for result in data.get("results", []):
            if result.get("issue_severity") in ["HIGH", "MEDIUM"]:
                findings.append({
                    "rule": result.get("test_id"),
                    "severity": result.get("issue_severity"),
                    "line": result.get("line_number"),
                    "message": result.get("issue_text")
                })
        return findings
    except Exception as e:
        logger.error("bandit_failed", error=str(e))
        return []

async def run_semgrep(path: str) -> List[Dict[str, Any]]:
    """Invokes Semgrep static analysis and returns findings.

    Args:
        path: The filesystem path to analyze.

    Returns:
        A list of dictionaries containing Semgrep findings.
    """
    cmd = ["semgrep", "--config=auto", "--json", path]
    
    ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
    
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
        findings = []
        for result in data.get("results", []):
            findings.append({
                "rule": result.get("check_id"),
                "severity": result.get("extra", {}).get("severity"),
                "line": result.get("start", {}).get("line"),
                "message": result.get("extra", {}).get("message")
            })
        return findings
    except Exception as e:
        logger.error("semgrep_failed", error=str(e))
        return []
