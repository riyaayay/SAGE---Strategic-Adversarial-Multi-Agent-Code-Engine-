"""
SAGE-PRO Routing Ledger
════════════════════════
Session-level log of all routing decisions + outcomes.
Used by the Daily Update Scheduler for batch Q-table updates.
"""

import time
import structlog
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = structlog.get_logger(__name__)


@dataclass
class RoutingEntry:
    """A single routing decision log entry."""
    timestamp: float
    user_id: str
    query_hash: str
    cluster_id: int
    action_idx: int
    agent_sequence: List[str]
    reward: Optional[float] = None
    correction_tier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RoutingLedger:
    """In-memory + persistent log of routing decisions."""

    def __init__(self) -> None:
        self.entries: List[RoutingEntry] = []
        logger.info("routing_ledger_initialized")

    def log(
        self,
        user_id: str,
        query_hash: str,
        cluster_id: int,
        action_idx: int,
        agent_sequence: List[str],
    ) -> int:
        """Logs a routing decision. Returns the entry index.

        Args:
            user_id: The user who made the query.
            query_hash: Hash of the query embedding.
            cluster_id: The FAISS cluster the query was routed to.
            action_idx: The Q-table action index selected.
            agent_sequence: Ordered list of agent names used.

        Returns:
            Index of the logged entry (for later reward annotation).
        """
        entry = RoutingEntry(
            timestamp=time.time(),
            user_id=user_id,
            query_hash=query_hash,
            cluster_id=cluster_id,
            action_idx=action_idx,
            agent_sequence=agent_sequence,
        )
        self.entries.append(entry)
        idx = len(self.entries) - 1
        logger.debug("routing_logged", index=idx, cluster=cluster_id, action=action_idx)
        return idx

    def annotate_reward(self, index: int, reward: float) -> None:
        """Annotates a logged entry with its observed reward.

        Args:
            index: The entry index returned by log().
            reward: The composite reward observed.
        """
        if 0 <= index < len(self.entries):
            self.entries[index].reward = reward
            logger.debug("reward_annotated", index=index, reward=reward)

    def annotate_correction(self, index: int, tier: str) -> None:
        """Annotates a logged entry with a correction tier.

        Args:
            index: The entry index.
            tier: 'hard' or 'soft'.
        """
        if 0 <= index < len(self.entries):
            self.entries[index].correction_tier = tier
            logger.debug("correction_annotated", index=index, tier=tier)

    def get_unprocessed(self) -> List[RoutingEntry]:
        """Returns entries that have rewards but haven't been batch-processed.

        Returns:
            List of RoutingEntry objects with non-None rewards.
        """
        return [e for e in self.entries if e.reward is not None]

    def clear_processed(self) -> int:
        """Removes processed entries from the ledger.

        Returns:
            Number of entries cleared.
        """
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.reward is None]
        cleared = original_count - len(self.entries)
        logger.info("ledger_cleared", cleared=cleared, remaining=len(self.entries))
        return cleared
