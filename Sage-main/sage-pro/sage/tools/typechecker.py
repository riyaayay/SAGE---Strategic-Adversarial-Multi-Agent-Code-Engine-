import structlog
from typing import List, Dict, Any
from sage.tools.sandbox import run_command_in_sandbox

logger = structlog.get_logger(__name__)

async def run_mypy(path: str) -> List[Dict[str, Any]]:
    """Invokes Mypy type checker and parses output.

    Args:
        path: Path to the python file.

    Returns:
        List of typing errors.
    """
    cmd = ["mypy", "--strict", "--no-color-output", "--no-error-summary", path]
    
    ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
    
    if not stdout:
        return []

    findings = []
    output_str = stdout.decode("utf-8", errors="ignore")
    for line in output_str.splitlines():
        # Mypy format: file:line: error_type: message
        parts = line.split(":", 3)
        if len(parts) >= 4:
            findings.append({
                "line": parts[1].strip(),
                "severity": parts[2].strip(),
                "message": parts[3].strip()
            })
            
    return findings
