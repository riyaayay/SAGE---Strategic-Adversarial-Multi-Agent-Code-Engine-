"""
SAGE-PRO Reward Crystallizer
═════════════════════════════
Computes composite reward signal from multi-dimensional quality metrics.

R = w_correctness × correctness
  + w_security   × security
  + w_efficiency  × efficiency
  + w_novelty     × novelty

Weights loaded from configs/aode_hyperparams.yaml → ctr_maqr.reward_weights.
"""

import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)


class RewardCrystallizer:
    """Computes composite reward from multi-dimensional quality scores."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes reward weights from config.

        Args:
            hyperparams: Full hyperparams dict (expects 'ctr_maqr.reward_weights').
        """
        cfg = hyperparams.get("ctr_maqr", {})
        rw = cfg.get("reward_weights", {})

        self.w_correctness: float = rw.get("correctness", 0.40)
        self.w_security: float = rw.get("security", 0.30)
        self.w_efficiency: float = rw.get("efficiency", 0.20)
        self.w_novelty: float = rw.get("novelty", 0.10)

        logger.info(
            "reward_crystallizer_initialized",
            weights={
                "correctness": self.w_correctness,
                "security": self.w_security,
                "efficiency": self.w_efficiency,
                "novelty": self.w_novelty,
            },
        )

    def compute(
        self,
        correctness: float,
        security: float,
        efficiency: float,
        novelty: float,
    ) -> float:
        """Computes the composite reward score.

        All input scores should be in [0, 1].

        Args:
            correctness: How correct is the generated code (tests pass rate).
            security: Security score (1 - vulnerability density).
            efficiency: Big-O / runtime efficiency score.
            novelty: Novelty of the approach vs. prior solutions.

        Returns:
            Composite reward in [0, 1].
        """
        reward = (
            self.w_correctness * correctness
            + self.w_security * security
            + self.w_efficiency * efficiency
            + self.w_novelty * novelty
        )

        # Clamp to [0, 1]
        reward = max(0.0, min(1.0, reward))

        logger.info(
            "reward_computed",
            correctness=correctness,
            security=security,
            efficiency=efficiency,
            novelty=novelty,
            composite=reward,
        )
        return reward

    def compute_with_ast_diff(
        self,
        correctness: float,
        security: float,
        efficiency: float,
        novelty: float,
        first_code: str = "",
        final_code: str = "",
        hyperparams: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Computes composite reward with AST diff penalty integration.

        When first_code and final_code are provided, the AST Delta Score
        (Novel System 4) replaces the traditional correctness signal
        with a deterministic, code-native measurement.

        The AST delta score measures how much the code had to change
        between the agent's first attempt and the final passing version.
        Higher delta (more changes) = lower reward.

        Args:
            correctness: Base correctness score [0, 1].
            security: Security score [0, 1].
            efficiency: Efficiency score [0, 1].
            novelty: Novelty score [0, 1].
            first_code: Agent's first code attempt (optional).
            final_code: Final passing code (optional).
            hyperparams: Config dict for AST reward weights.

        Returns:
            Composite reward in [0, 1], with AST diff integrated.
        """
        base_reward = self.compute(correctness, security, efficiency, novelty)

        if not first_code or not final_code:
            return base_reward

        try:
            from sage.core.ast_diff_reward import ASTDiffRewardCrystallizer
            ast_reward = ASTDiffRewardCrystallizer(hyperparams or {})
            delta = ast_reward.compute_code_delta_score(first_code, final_code)
            ast_score = delta["delta_score"]

            # Blend: 60% AST-grounded, 40% traditional
            blended = 0.6 * ast_score + 0.4 * base_reward
            blended = max(0.0, min(1.0, blended))

            logger.info(
                "reward_with_ast_diff",
                base=base_reward,
                ast_delta=ast_score,
                blended=blended,
            )
            return blended

        except Exception as e:
            logger.warning("ast_diff_fallback", error=str(e))
            return base_reward

