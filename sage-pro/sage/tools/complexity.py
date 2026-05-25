import structlog
from typing import Dict, Any, List
from radon.complexity import cc_visit
from radon.metrics import mi_visit

logger = structlog.get_logger(__name__)

def cyclomatic_complexity(code: str) -> Dict[str, Any]:
    """Calculates Cyclomatic Complexity using Radon.

    Args:
        code: The Python source code to analyze.

    Returns:
        A dictionary containing complexity metrics per block.
    """
    try:
        results = cc_visit(code)
        blocks = []
        total_cc = 0
        for block in results:
            blocks.append({
                "name": block.name,
                "complexity": block.complexity,
                "rank": block.rank
            })
            total_cc += block.complexity
            
        return {
            "blocks": blocks,
            "average_complexity": total_cc / len(blocks) if blocks else 0
        }
    except Exception as e:
        logger.error("complexity_calc_failed", error=str(e))
        return {"blocks": [], "average_complexity": 0}

def maintainability_index(code: str) -> float:
    """Calculates the Maintainability Index using Radon.

    Args:
        code: The Python source code to analyze.

    Returns:
        The maintainability index score (0-100).
    """
    try:
        return float(mi_visit(code, multi=False))
    except Exception as e:
        logger.error("mi_calc_failed", error=str(e))
        return 0.0
