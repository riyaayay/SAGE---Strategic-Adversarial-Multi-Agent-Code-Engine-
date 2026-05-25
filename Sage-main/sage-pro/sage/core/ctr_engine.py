"""
SAGE-PRO CTR Engine & MAQR (Manifold-Adaptive Q-Routing)
═════════════════════════════════════════════════════════
Implements Q-learning on the FAISS centroid manifold.

State  s = (query_embedding, cluster_id, user_id)
Action a = (agent_sequence, adapter_index)
Reward r = weighted composite from reward_crystallizer

Q(s,a) ← Q(s,a) + α × [r + γ × max_a' Q(s', a') − Q(s,a)]

All hyperparameters loaded from configs/aode_hyperparams.yaml → ctr_maqr.
"""

import numpy as np
import pickle
import structlog
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from collections import defaultdict

logger = structlog.get_logger(__name__)


class CTREngine:
    """Centroid Topology Routing — Q-learning on the FAISS manifold."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the CTR engine from config.

        Args:
            hyperparams: Full hyperparams dict (expects 'ctr_maqr' key).
        """
        cfg = hyperparams.get("ctr_maqr", {})
        ql = cfg.get("q_learning", {})

        self.alpha: float = ql.get("alpha", 0.15)
        self.gamma: float = ql.get("gamma", 0.92)
        self.epsilon_start: float = ql.get("epsilon_start", 0.25)
        self.epsilon_end: float = ql.get("epsilon_end", 0.04)

        # Q-table: maps (cluster_id, action_idx) → Q-value
        self.q_table: Dict[Tuple[int, int], float] = defaultdict(float)

        # Exploration rate per agent (decays over time)
        self.agent_epsilons: Dict[str, float] = {}

        logger.info(
            "ctr_engine_initialized",
            alpha=self.alpha,
            gamma=self.gamma,
            epsilon_range=f"{self.epsilon_start}→{self.epsilon_end}",
        )

    def get_epsilon(self, agent_name: str) -> float:
        """Gets the current exploration rate for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Current epsilon value.
        """
        return self.agent_epsilons.get(agent_name, self.epsilon_start)

    def select_action(
        self,
        cluster_id: int,
        num_actions: int,
        agent_name: str,
    ) -> int:
        """Epsilon-greedy action selection.

        Args:
            cluster_id: The current cluster/state ID.
            num_actions: Total number of possible actions.
            agent_name: Name of the agent (for per-agent epsilon).

        Returns:
            The selected action index.
        """
        eps = self.get_epsilon(agent_name)

        if np.random.random() < eps:
            # Explore
            action = np.random.randint(0, num_actions)
            logger.debug("ctr_action_explore", agent=agent_name, action=action)
        else:
            # Exploit — pick the action with highest Q-value
            q_values = [
                self.q_table.get((cluster_id, a), 0.0) for a in range(num_actions)
            ]
            action = int(np.argmax(q_values))
            logger.debug("ctr_action_exploit", agent=agent_name, action=action)

        return action

    def update(
        self,
        cluster_id: int,
        action: int,
        reward: float,
        next_cluster_id: Optional[int] = None,
        num_actions: int = 4,
    ) -> float:
        """Performs a single Q-learning update.

        Q(s,a) ← Q(s,a) + α × [r + γ × max_a' Q(s', a') − Q(s,a)]

        Args:
            cluster_id: Current state (cluster ID).
            action: Action taken.
            reward: Observed reward.
            next_cluster_id: Next state (cluster ID). None if terminal.
            num_actions: Number of possible actions.

        Returns:
            The TD error (delta).
        """
        current_q = self.q_table.get((cluster_id, action), 0.0)

        if next_cluster_id is not None:
            future_q = max(
                self.q_table.get((next_cluster_id, a), 0.0)
                for a in range(num_actions)
            )
        else:
            future_q = 0.0

        td_target = reward + self.gamma * future_q
        td_error = td_target - current_q
        new_q = current_q + self.alpha * td_error

        self.q_table[(cluster_id, action)] = new_q

        logger.debug(
            "q_update",
            state=cluster_id,
            action=action,
            reward=reward,
            old_q=current_q,
            new_q=new_q,
            td_error=td_error,
        )
        return td_error

    def save(self, path: str = "data/q_table.pkl") -> None:
        """Persists the Q-table to disk.

        Args:
            path: File path for the pickle file.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(dict(self.q_table), f)
        logger.info("q_table_saved", path=path, entries=len(self.q_table))

    def load(self, path: str = "data/q_table.pkl") -> None:
        """Loads the Q-table from disk.

        Args:
            path: File path for the pickle file.
        """
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.q_table = defaultdict(float, data)
            logger.info("q_table_loaded", path=path, entries=len(self.q_table))
        except FileNotFoundError:
            logger.warning("q_table_not_found", path=path)
