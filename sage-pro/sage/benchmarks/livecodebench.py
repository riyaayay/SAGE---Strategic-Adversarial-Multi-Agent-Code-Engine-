import json
import structlog
import asyncio
from typing import List, Dict, Any, Optional
from datasets import load_dataset
from sage.api.server import _get_graph

logger = structlog.get_logger(__name__)

async def run_livecodebench(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Evaluates SAGE-PRO against LiveCodeBench (generation lite)."""
    logger.info("loading_livecodebench")
    # Using the generation lite split if available
    try:
        dataset = load_dataset("livecodebench/livecodebench", split="test")
    except:
        logger.warning("livecodebench_load_failed_falling_back")
        return []
    
    problems = list(dataset)
    if limit:
        problems = problems[:limit]
        
    results = []
    graph = _get_graph()
    
    for problem in problems:
        question_id = problem.get("question_id", "unknown")
        logger.info("evaluating_live_problem", id=question_id)
        
        try:
            state = await graph.ainvoke({"request": {"task": problem["question_content"], "max_cycles": 3}})
            solution = state.get("final_code", "")
        except Exception as e:
            logger.error("problem_failed", id=question_id, error=str(e))
            solution = ""

        results.append({
            "question_id": question_id,
            "solution": solution,
            "complexity": problem.get("difficulty", "medium")
        })
        
    with open("benchmarks/results/livecodebench.json", "w") as f:
        json.dump(results, f, indent=2)
        
    return results
