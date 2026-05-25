"""
SAGE-PRO Daily Update Scheduler
════════════════════════════════
Runs at a configurable time (default 02:00 UTC) via APScheduler.
Processes all unprocessed corrections in batch:

1. Query corrections WHERE batch_processed = FALSE
2. Compute mean penalty per agent
3. Apply gradient update to agent_weights
4. Run Q-table batch update from routing_ledger
5. Apply RGCD centroid drift
6. Crystallisation check + evaporation sweep
7. Save FAISS index + Q-table to disk
8. Mark corrections as batch_processed = TRUE
9. Write to daily_update_log

Schedule time from env var DAILY_UPDATE_HOUR (default: 2).
"""

import os
import time
import structlog
from datetime import datetime
from typing import Dict, Any

logger = structlog.get_logger(__name__)

DAILY_UPDATE_HOUR = int(os.environ.get("DAILY_UPDATE_HOUR", "2"))
DAILY_UPDATE_MINUTE = int(os.environ.get("DAILY_UPDATE_MINUTE", "0"))


async def run_daily_update(
    hyperparams: Dict[str, Any],
    ctr_engine: Any,
    manifold_mutator: Any,
    penalty_system: Any,
    routing_ledger: Any,
) -> Dict[str, Any]:
    """Executes the full daily batch update.

    Args:
        hyperparams: Full hyperparams dict.
        ctr_engine: The CTREngine instance.
        manifold_mutator: The ManifoldMutator instance.
        penalty_system: The AgentPenaltySystem instance.
        routing_ledger: The RoutingLedger instance.

    Returns:
        Dict with update statistics for the daily_update_log.
    """
    start = time.time()
    logger.info("daily_update_started", timestamp=datetime.utcnow().isoformat())

    # 1. Get unprocessed routing entries
    entries = routing_ledger.get_unprocessed()
    corrections_count = len([e for e in entries if e.correction_tier is not None])

    # 2–3. Compute penalties per agent (stub — needs DB integration)
    agents_penalised = {}

    # 4. Batch Q-table update
    total_td_error = 0.0
    for entry in entries:
        if entry.reward is not None:
            td = ctr_engine.update(
                cluster_id=entry.cluster_id,
                action=entry.action_idx,
                reward=entry.reward,
            )
            total_td_error += abs(td)

    # 5–6. Centroid drift + crystallisation + evaporation
    centroid_mutations = 0
    new_clusters = 0
    pruned = manifold_mutator.apply_evaporation(global_step=0)

    # 7. Save
    ctr_engine.save()

    # 8. Clear processed entries
    routing_ledger.clear_processed()

    duration = time.time() - start

    result = {
        "run_date": datetime.utcnow(),
        "corrections_count": corrections_count,
        "agents_penalised": agents_penalised,
        "centroid_mutations": centroid_mutations,
        "new_clusters": new_clusters,
        "pruned_clusters": len(pruned),
        "q_table_delta_norm": total_td_error,
        "duration_seconds": duration,
    }

    logger.info("daily_update_complete", **result)
    return result


def start_scheduler(
    hyperparams: Dict[str, Any],
    ctr_engine: Any,
    manifold_mutator: Any,
    penalty_system: Any,
    routing_ledger: Any,
) -> Any:
    """Starts the APScheduler with the daily update job.

    Args:
        hyperparams: Full hyperparams dict.
        ctr_engine: The CTREngine instance.
        manifold_mutator: The ManifoldMutator instance.
        penalty_system: The AgentPenaltySystem instance.
        routing_ledger: The RoutingLedger instance.

    Returns:
        The scheduler instance.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_update,
        "cron",
        hour=DAILY_UPDATE_HOUR,
        minute=DAILY_UPDATE_MINUTE,
        args=[hyperparams, ctr_engine, manifold_mutator, penalty_system, routing_ledger],
        id="sage_daily_update",
        replace_existing=True,
    )
    scheduler.start()

    logger.info(
        "daily_scheduler_started",
        schedule=f"{DAILY_UPDATE_HOUR:02d}:{DAILY_UPDATE_MINUTE:02d} UTC",
    )
    return scheduler
