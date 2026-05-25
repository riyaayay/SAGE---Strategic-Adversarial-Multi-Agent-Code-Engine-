import json
import structlog
import os
import tempfile
from typing import Dict, Any
from sage.tools.sandbox import run_command_in_sandbox

logger = structlog.get_logger(__name__)

async def run_hyperfine(cmd_str: str, runs: int = 5) -> Dict[str, Any]:
    """Invokes Hyperfine benchmarking tool and returns results.

    Args:
        cmd_str: The shell command to benchmark.
        runs: Number of benchmark runs.

    Returns:
        A dictionary containing benchmarking statistics.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        report_file = f.name

    try:
        # We run hyperfine on the host but via the sandbox logic if needed.
        # Hyperfine is usually a system tool.
        cmd = ["hyperfine", "--export-json", report_file, "-n", "SageBench", "-r", str(runs), cmd_str]
        
        ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
        
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                data = json.load(f)
                return data.get("results", [{}])[0]
        return {"error": "No benchmark report generated"}
    except Exception as e:
        logger.error("hyperfine_failed", error=str(e))
        return {"error": str(e)}
    finally:
        if os.path.exists(report_file):
            os.remove(report_file)

async def run_pyperf(script_path: str) -> Dict[str, Any]:
    """Fallback benchmarker using pyperf when hyperfine is unavailable.

    Args:
        script_path: The Python script to profile.

    Returns:
        A dictionary containing pyperf statistics.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        report_file = f.name

    try:
        cmd = ["python3", "-m", "pyperf", "run", "-o", report_file, script_path]
        ret_code, stdout, stderr = await run_command_in_sandbox(cmd)
        
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                return json.load(f)
        return {"error": "No pyperf report generated"}
    except Exception as e:
        logger.error("pyperf_failed", error=str(e))
        return {"error": str(e)}
    finally:
        if os.path.exists(report_file):
            os.remove(report_file)
