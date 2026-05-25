from sage.tools.linter import run_ruff
from sage.tools.typechecker import run_mypy
from sage.tools.security import run_bandit
from sage.tools.sandbox import run_in_sandbox
from sage.tools.complexity import cyclomatic_complexity
from typing import Dict, Any
import tempfile
import asyncio
import os

async def evaluate_code(code: str, tests: str) -> Dict[str, Any]:
    """Runs the mechanical tool oracle and computes a unified damage score.

    This function aggregates findings from the linter, type-checker, security 
    scanner, sandbox execution, and complexity analyzer.

    Args:
        code: The Python implementation code to evaluate.
        tests: The test cases to run against the code.

    Returns:
        Dict containing the tool findings and the aggregated damage score.
    """
    # Write code to a temp file for tools that need paths
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = f.name

    try:
        # Parallel tool execution could be implemented here for speed
        ruff_res, mypy_res, sec_res, sandbox_res = await asyncio.gather(
            run_ruff(temp_path),
            run_mypy(temp_path),
            run_bandit(temp_path),
            run_in_sandbox(code, tests)
        )
        comp_res = cyclomatic_complexity(code)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    # Calculate damage (0.0 to 1.0+)
    # This represents the 'Damage Function' from the Nash Crucible.
    damage = 0.0
    damage += len(ruff_res) * 0.1
    damage += len(mypy_res) * 0.4
    damage += len(sec_res) * 0.8
    # sandbox_res is ToolReport, so we check tests_passed
    damage += (0.0 if getattr(sandbox_res, "tests_passed", False) else 1.0)
    damage += max(0, (comp_res.get("avg_cyclomatic_complexity", 0) - 10) * 0.2)
    
    return {
        "total_damage": min(damage, 2.0),
        "ruff": ruff_res,
        "mypy": mypy_res,
        "security": sec_res,
        "sandbox": sandbox_res,
        "complexity": comp_res
    }
