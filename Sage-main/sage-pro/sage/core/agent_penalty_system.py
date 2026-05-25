"""
SAGE-PRO Agent Penalty System
═════════════════════════════
Implements hard/soft penalty + exploration-boost after corrections.

Hard penalty (confident wrong answer):
    W_new = W - alpha_hard × (W - w_floor)^0.5

Soft penalty (partially wrong):
    W_new = W - alpha_soft × (W - w_floor)

Exploration boost (after every penalty):
    epsilon_new = min(epsilon + epsilon_boost, epsilon_max)
    epsilon decays at epsilon_decay per step back toward baseline

All constants loaded from configs/aode_hyperparams.yaml → penalty block.
"""

import math
import structlog
from typing import Dict, Any, Tuple

logger = structlog.get_logger(__name__)


class AgentPenaltySystem:
    """Manages per-agent weights and exploration rates."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the penalty system from config.

        Args:
            hyperparams: Full hyperparams dict (expects a 'penalty' key).
        """
        pen = hyperparams.get("penalty", {})
        self.alpha_hard: float = pen.get("alpha_hard", 0.25)
        self.alpha_soft: float = pen.get("alpha_soft", 0.08)
        self.w_floor: float = pen.get("w_floor", 0.10)
        self.epsilon_boost: float = pen.get("epsilon_boost", 0.30)
        self.epsilon_max: float = pen.get("epsilon_max", 0.90)
        self.epsilon_decay: float = pen.get("epsilon_decay", 0.97)

        logger.info(
            "penalty_system_initialized",
            alpha_hard=self.alpha_hard,
            alpha_soft=self.alpha_soft,
            w_floor=self.w_floor,
        )

    def apply_hard_penalty(self, weight: float, epsilon: float) -> Tuple[float, float]:
        """Applies a hard penalty for a confidently wrong answer.

        The square-root term penalises high-performing agents more steeply.
        An agent at W=0.95 loses more than one at W=0.50.

        Args:
            weight: Current agent weight.
            epsilon: Current exploration rate.

        Returns:
            Tuple of (new_weight, new_epsilon).
        """
        delta = self.alpha_hard * math.sqrt(max(weight - self.w_floor, 0.0))
        new_weight = max(weight - delta, self.w_floor)
        new_epsilon = min(epsilon + self.epsilon_boost, self.epsilon_max)

        logger.info(
            "hard_penalty_applied",
            old_weight=weight,
            new_weight=new_weight,
            delta=delta,
            new_epsilon=new_epsilon,
        )
        return new_weight, new_epsilon

    def apply_soft_penalty(self, weight: float, epsilon: float) -> Tuple[float, float]:
        """Applies a soft penalty for a partially wrong answer.

        Linear decay — less aggressive than hard penalty.

        Args:
            weight: Current agent weight.
            epsilon: Current exploration rate.

        Returns:
            Tuple of (new_weight, new_epsilon).
        """
        delta = self.alpha_soft * max(weight - self.w_floor, 0.0)
        new_weight = max(weight - delta, self.w_floor)
        new_epsilon = min(epsilon + self.epsilon_boost, self.epsilon_max)

        logger.info(
            "soft_penalty_applied",
            old_weight=weight,
            new_weight=new_weight,
            delta=delta,
            new_epsilon=new_epsilon,
        )
        return new_weight, new_epsilon

    def decay_epsilon(self, epsilon: float, baseline: float = 0.15) -> float:
        """Decays epsilon back toward baseline after exploration boost.

        Called once per step after a penalty event.

        Args:
            epsilon: Current exploration rate.
            baseline: Target resting epsilon.

        Returns:
            The decayed epsilon value.
        """
        new_epsilon = baseline + (epsilon - baseline) * self.epsilon_decay
        return max(new_epsilon, baseline)
