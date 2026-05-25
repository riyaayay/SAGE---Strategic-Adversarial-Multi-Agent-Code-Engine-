import asyncio
import os
import tempfile
import json
import shutil
import structlog
from pathlib import Path
from typing import Optional
from sage.core.types import ToolReport

logger = structlog.get_logger(__name__)

async def run_command_in_sandbox(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = 30
) -> tuple[int, bytes, bytes]:
    """Runs a generic command inside the secure sandbox.

    Args:
        cmd: The command and its arguments.
        cwd: Optional working directory.
        timeout: Execution timeout.

    Returns:
        A tuple of (return_code, stdout, stderr).
    """
    wrapper = []
    if shutil.which("firejail"):
        wrapper = ["firejail", "--quiet", "--net=none", "--private", "--rlimit-as=1G", f"--timeout=00:00:{timeout}"]
    elif shutil.which("bwrap"):
        wrapper = ["bwrap", "--unshare-all", "--share-net", "false", "--dev", "/dev", "--proc", "/proc"]
        # Note: bwrap requires explicit binds which depend on the host; simplified here.
    
    full_cmd = wrapper + cmd
    try:
        process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout + 5)
            return process.returncode or 0, stdout, stderr
        except asyncio.TimeoutError:
            process.kill()
            return -1, b"", b"Timeout"
    except Exception as e:
        logger.error("sandbox_command_failed", error=str(e))
        return -1, b"", str(e).encode()

async def run_in_sandbox(
    code: str, 
    tests: str, 
    timeout: int = 30
) -> ToolReport:
    """Executes code and tests within a secure sandbox environment."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        code_file = tmp_path / "solution.py"
        test_file = tmp_path / "test_solution.py"
        report_file = tmp_path / "report.json"

        code_file.write_text(code, encoding="utf-8")
        test_file.write_text(f"from solution import *\\n\\n{tests}", encoding="utf-8")

        cmd = [
            "python3", "-m", "pytest", str(test_file), 
            f"--json-report", f"--json-report-file={report_file}"
        ]

        ret_code, stdout, stderr = await run_command_in_sandbox(cmd, cwd=tmp_dir, timeout=timeout)

        if report_file.exists():
            with open(report_file, "r") as f:
                report_data = json.load(f)
                summary = report_data.get("summary", {})
                passed = summary.get("passed", 0)
                total = summary.get("total", 0)
                tests_passed = passed == total and total > 0
                
                return ToolReport(
                    tests_passed=tests_passed,
                    coverage=report_data.get("coverage", {}).get("percent_covered", 0.0),
                    total_damage=0.0 if tests_passed else 0.5
                )
        
        success = ret_code == 0
        return ToolReport(
            tests_passed=success,
            total_damage=0.0 if success else 1.0
        )
