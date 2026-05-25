import json
import structlog
import asyncio
from typing import List, Dict, Any, Optional
from datasets import load_dataset
from sage.api.server import _get_graph

logger = structlog.get_logger(__name__)

async def run_swe_bench_lite(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Evaluates SAGE-PRO against the SWE-bench_Lite dataset.

    Args:
        limit: Max number of issues to evaluate.

    Returns:
        List of results including generated patches.
    """
    logger.info("loading_swe_bench_lite")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    issues = list(dataset)
    if limit:
        issues = issues[:limit]
        
    results = []
    graph = _get_graph()
    
    for issue in issues:
        instance_id = issue["instance_id"]
        logger.info("evaluating_issue", instance_id=instance_id)
        
        try:
            task = f"Solve the following issue in the repository:\\n{issue['problem_statement']}"
            state = await graph.ainvoke({"request": {"task": task, "max_cycles": 5}})
            patch = state.get("final_code", "")
        except Exception as e:
            logger.error("issue_failed", instance_id=instance_id, error=str(e))
            patch = ""

        results.append({
            "instance_id": instance_id,
            "patch": patch,
            "found_by_sage": True
        })
        
    with open("benchmarks/results/swe_bench_lite.json", "w") as f:
        json.dump(results, f, indent=2)
        
    return results
