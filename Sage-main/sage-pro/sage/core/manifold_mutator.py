"""
SAGE-PRO Manifold Mutator
══════════════════════════
Implements FAISS centroid drift, crystallisation, and evaporation.

Centroid Drift (RGCD):
    if r >= high_threshold: centroid += attract_rate × (query_emb - centroid)
    if r <= low_threshold:  centroid -= repel_rate  × (query_emb - centroid)

Crystallisation:
    N consecutive high-reward interactions → spawn new micro-cluster

Evaporation:
    Cluster idle for M steps → weight × decay_rate per step → pruned below threshold

All parameters from configs/aode_hyperparams.yaml → ctr_maqr.
"""

import numpy as np
import faiss
import structlog
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = structlog.get_logger(__name__)


class ManifoldMutator:
    """Manages dynamic mutations of the FAISS routing manifold."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the mutator from config.

        Args:
            hyperparams: Full hyperparams dict (expects 'ctr_maqr' key).
        """
        cfg = hyperparams.get("ctr_maqr", {})
        drift = cfg.get("centroid_drift", {})
        evap = cfg.get("evaporation", {})

        # Centroid drift parameters
        self.high_reward_threshold: float = drift.get("high_reward_threshold", 0.75)
        self.low_reward_threshold: float = drift.get("low_reward_threshold", 0.35)
        self.attract_rate: float = drift.get("attract_rate", 0.08)
        self.repel_rate: float = drift.get("repel_rate", 0.04)

        # Crystallisation
        self.crystal_consecutive: int = cfg.get("crystallisation_consecutive_steps", 5)

        # Evaporation
        self.idle_threshold: int = evap.get("idle_steps_threshold", 500)
        self.decay_rate: float = evap.get("decay_rate", 0.98)
        self.prune_threshold: float = evap.get("prune_threshold", 0.01)

        # Internal tracking
        self.cluster_visit_count: Dict[int, int] = defaultdict(int)
        self.cluster_idle_steps: Dict[int, int] = defaultdict(int)
        self.cluster_weights: Dict[int, float] = defaultdict(lambda: 1.0)
        self.consecutive_high_rewards: Dict[int, int] = defaultdict(int)
        self.reward_buffer: Dict[int, List[np.ndarray]] = defaultdict(list)

        logger.info(
            "manifold_mutator_initialized",
            attract=self.attract_rate,
            repel=self.repel_rate,
            crystal_steps=self.crystal_consecutive,
            idle_thresh=self.idle_threshold,
        )

    def apply_centroid_drift(
        self,
        centroid: np.ndarray,
        query_embedding: np.ndarray,
        reward: float,
    ) -> np.ndarray:
        """Applies centroid drift based on reward signal.

        High reward → attract centroid toward the query.
        Low reward → repel centroid away from the query.

        Args:
            centroid: Current centroid vector.
            query_embedding: The query that produced this reward.
            reward: Composite reward score [0, 1].

        Returns:
            The updated centroid vector.
        """
        diff = query_embedding - centroid

        if reward >= self.high_reward_threshold:
            centroid = centroid + self.attract_rate * diff
            logger.debug("centroid_attracted", reward=reward)
        elif reward <= self.low_reward_threshold:
            centroid = centroid - self.repel_rate * diff
            logger.debug("centroid_repelled", reward=reward)

        return centroid

    def check_crystallisation(
        self,
        cluster_id: int,
        query_embedding: np.ndarray,
        reward: float,
    ) -> Optional[np.ndarray]:
        """Checks if a new micro-cluster should be spawned.

        After N consecutive high-reward interactions in a cluster,
        spawn a new cluster at the mean embedding.

        Args:
            cluster_id: The cluster being tracked.
            query_embedding: The current query embedding.
            reward: The current reward.

        Returns:
            The new cluster centroid if crystallisation triggered, else None.
        """
        if reward >= self.high_reward_threshold:
            self.consecutive_high_rewards[cluster_id] += 1
            self.reward_buffer[cluster_id].append(query_embedding)
        else:
            self.consecutive_high_rewards[cluster_id] = 0
            self.reward_buffer[cluster_id] = []

        if self.consecutive_high_rewards[cluster_id] >= self.crystal_consecutive:
            embeddings = np.array(self.reward_buffer[cluster_id])
            new_centroid = embeddings.mean(axis=0)

            # Reset tracking
            self.consecutive_high_rewards[cluster_id] = 0
            self.reward_buffer[cluster_id] = []

            logger.info(
                "crystallisation_triggered",
                cluster_id=cluster_id,
                consecutive_highs=self.crystal_consecutive,
            )
            return new_centroid

        return None

    def apply_evaporation(self, global_step: int) -> List[int]:
        """Applies evaporation to idle clusters.

        Clusters not visited for idle_threshold steps have their weight
        decayed. If weight falls below prune_threshold, they are pruned.

        Args:
            global_step: Current global step counter.

        Returns:
            List of cluster IDs that were pruned.
        """
        pruned = []

        for cluster_id in list(self.cluster_idle_steps.keys()):
            idle = self.cluster_idle_steps[cluster_id]
            if idle >= self.idle_threshold:
                self.cluster_weights[cluster_id] *= self.decay_rate

                if self.cluster_weights[cluster_id] < self.prune_threshold:
                    pruned.append(cluster_id)
                    logger.info("cluster_pruned", cluster_id=cluster_id, idle_steps=idle)

        # Clean up pruned clusters
        for cid in pruned:
            del self.cluster_idle_steps[cid]
            del self.cluster_weights[cid]
            self.consecutive_high_rewards.pop(cid, None)
            self.reward_buffer.pop(cid, None)

        if pruned:
            logger.info("evaporation_sweep_complete", pruned_count=len(pruned))

        return pruned

    def record_visit(self, cluster_id: int) -> None:
        """Records a visit to a cluster, resetting its idle counter.

        Args:
            cluster_id: The visited cluster ID.
        """
        self.cluster_visit_count[cluster_id] += 1
        self.cluster_idle_steps[cluster_id] = 0

        # Increment idle counters for all OTHER clusters
        for cid in self.cluster_idle_steps:
            if cid != cluster_id:
                self.cluster_idle_steps[cid] += 1
