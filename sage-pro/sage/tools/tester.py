import structlog
from typing import Dict, Any
from sage.tools.sandbox import run_in_sandbox

logger = structlog.get_logger(__name__)

async def run_pytest(
    code_path: str, 
    test_path: str, 
    timeout: int = 30
) -> Dict[str, Any]:
    """Runs pytest in the sandbox and returns detailed results.

    Args:
        code_path: The filesystem path to the code.
        test_path: The filesystem path to the tests.
        timeout: Execution timeout in seconds.

    Returns:
        A dictionary containing {passed, failed, errors, coverage_pct, durations}.
    """
    with open(code_path, "r") as f:
        code = f.read()
    with open(test_path, "r") as f:
        tests = f.read()
        
    report = await run_in_sandbox(code, tests, timeout=timeout)
    
    # We'll need to expand ToolReport or parse raw json if more detail is needed.
    # For now, we return a compatible dictionary.
    return {
        "passed": report.tests_passed,
        "failed": not report.tests_passed,
        "errors": 0 if report.tests_passed else 1,
        "coverage_pct": report.coverage,
        "durations": {} # Placeholder if not available from ToolReport yet
    }
