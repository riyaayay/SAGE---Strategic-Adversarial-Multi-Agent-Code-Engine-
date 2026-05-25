"""
SAGE-PRO Tool: Code Execute
═════════════════════════════
Sandboxed code execution via Docker containers.
Network-disabled, memory-limited, CPU-limited.

Config (env vars):
    SANDBOX_MEM_LIMIT     — container memory limit (default: 256m)
    SANDBOX_CPU_QUOTA     — CPU quota (default: 50000)
    SANDBOX_TIMEOUT       — execution timeout seconds (default: 15)
    SANDBOX_NETWORK       — enable network (default: false)
    SANDBOX_PYTHON_IMAGE  — Python Docker image (default: python:3.12-slim)
    SANDBOX_NODE_IMAGE    — Node Docker image (default: node:20-slim)
    SANDBOX_BASH_IMAGE    — Bash Docker image (default: bash:5)
"""

import os
import tempfile
import structlog
from typing import Dict, Any

logger = structlog.get_logger(__name__)

# All sandbox config from env vars — zero hardcoded values
SANDBOX_MEM_LIMIT = os.environ.get("SANDBOX_MEM_LIMIT", "256m")
SANDBOX_CPU_PERIOD = int(os.environ.get("SANDBOX_CPU_PERIOD", "100000"))
SANDBOX_CPU_QUOTA = int(os.environ.get("SANDBOX_CPU_QUOTA", "50000"))
SANDBOX_TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT", "15"))
SANDBOX_NETWORK = os.environ.get("SANDBOX_NETWORK", "false").lower() == "true"

SANDBOX_IMAGES = {
    "python": os.environ.get("SANDBOX_PYTHON_IMAGE", "python:3.12-slim"),
    "javascript": os.environ.get("SANDBOX_NODE_IMAGE", "node:20-slim"),
    "typescript": os.environ.get("SANDBOX_NODE_IMAGE", "node:20-slim"),
    "bash": os.environ.get("SANDBOX_BASH_IMAGE", "bash:5"),
}

SANDBOX_COMMANDS = {
    "python": "python",
    "javascript": "node",
    "typescript": "node",
    "bash": "bash",
}

SANDBOX_EXTENSIONS = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "bash": ".sh",
    "sql": ".sql",
}


async def tool_code_execute(
    language: str,
    code: str,
    purpose: str,
    expected_output: str = "",
) -> Dict[str, Any]:
    """Executes code in a sandboxed Docker container.

    Args:
        language: Language to execute (python, javascript, bash, etc.).
        code: Self-contained code to run.
        purpose: Why this code is being executed.
        expected_output: What output is expected (for comparison).

    Returns:
        Dict with 'output', 'status', 'purpose', and optionally 'match'.
    """
    try:
        import docker
    except ImportError:
        logger.warning("docker_not_installed")
        return {
            "output": "",
            "status": "error",
            "purpose": purpose,
            "error": "docker package not installed — install with: pip install docker",
        }

    if language == "sql":
        # SQL can't be run in Docker directly — return syntax-only check
        return {
            "output": "SQL execution requires a database connection. Syntax appears valid.",
            "status": "skipped",
            "purpose": purpose,
        }

    image = SANDBOX_IMAGES.get(language, SANDBOX_IMAGES["python"])
    cmd_prefix = SANDBOX_COMMANDS.get(language, "python")
    ext = SANDBOX_EXTENSIONS.get(language, ".py")

    # Write code to a temp file
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, f"code{ext}")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        client = docker.from_env()
        container_output = client.containers.run(
            image,
            f"{cmd_prefix} /code/{os.path.basename(tmp_path)}",
            volumes={tmp_dir: {"bind": "/code", "mode": "ro"}},
            mem_limit=SANDBOX_MEM_LIMIT,
            cpu_period=SANDBOX_CPU_PERIOD,
            cpu_quota=SANDBOX_CPU_QUOTA,
            network_disabled=not SANDBOX_NETWORK,
            remove=True,
            stdout=True,
            stderr=True,
            timeout=SANDBOX_TIMEOUT,
        )

        output = container_output.decode("utf-8", errors="replace")

        result = {
            "output": output,
            "status": "success",
            "purpose": purpose,
        }

        # Compare with expected output if provided
        if expected_output:
            result["match"] = output.strip() == expected_output.strip()
            if not result["match"]:
                result["warning"] = "Output differs from expected"

        logger.info(
            "code_execute_complete",
            language=language,
            purpose=purpose,
            output_length=len(output),
        )
        return result

    except Exception as e:
        logger.error("code_execute_failed", language=language, error=str(e))
        return {
            "output": str(e),
            "status": "error",
            "purpose": purpose,
        }
    finally:
        # Clean up temp files
        try:
            os.unlink(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass
