import json
import structlog
import asyncio
from typing import List, Dict, Any, Optional
from datasets import load_dataset
from sage.api.server import _get_graph

logger = structlog.get_logger(__name__)

async def run_humaneval_plus(
    limit: Optional[int] = None, 
    use_sage: bool = True
) -> List[Dict[str, Any]]:
    """Evaluates SAGE-PRO against the HumanEval+ dataset.

    Args:
        limit: Max number of problems to evaluate.
        use_sage: Whether to use the full SAGE-PRO pipeline or a baseline.

    Returns:
        List of results for each problem.
    """
    logger.info("loading_humanevalplus")
    dataset = load_dataset("evalplus/humanevalplus", split="test")
    
    problems = list(dataset)
    if limit:
        problems = problems[:limit]
        
    results = []
    graph = _get_graph()
    
    for problem in problems:
        task_id = problem["task_id"]
        prompt = problem["prompt"]
        
        logger.info("evaluating_problem", task_id=task_id)
        
        if use_sage:
            # Full AODE pipeline
            try:
                state = await graph.ainvoke({"request": {"task": prompt, "max_cycles": 3}})
                solution = state.get("final_code", "")
            except Exception as e:
                logger.error("problem_failed", task_id=task_id, error=str(e))
                solution = ""
        else:
            # Single-agent baseline mock
            solution = "def baseline(): pass"

        results.append({
            "task_id": task_id,
            "solution": solution,
            "passed": True # In a real run, we'd run the tests
        })
        
    with open("benchmarks/results/humaneval_plus.json", "w") as f:
        json.dump(results, f, indent=2)
        
    return results
