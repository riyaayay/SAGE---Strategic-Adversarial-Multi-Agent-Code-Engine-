"""
SAGE-PRO Correction Detector
═════════════════════════════
Detects user corrections in real-time using:
  1. Pattern matching — regex across configurable correction signal patterns
  2. Semantic contradiction — embedding cosine similarity check
  3. Explicit UI signal — thumbs-down button

Detection tiers:
  HARD — 2+ pattern matches OR thumbs-down → confident wrong answer
  SOFT — 1 pattern match OR semantic contradiction → partial error

All patterns loaded from configs/aode_hyperparams.yaml → correction_patterns.
"""

import re
import numpy as np
import structlog
from typing import Dict, Any, List, Optional
from enum import Enum

logger = structlog.get_logger(__name__)


class CorrectionTier(str, Enum):
    """Severity tier for a detected correction."""
    HARD = "hard"
    SOFT = "soft"
    NONE = "none"


class CorrectionDetector:
    """Detects when a user is correcting the AI's response."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the detector with configurable patterns.

        Args:
            hyperparams: Full hyperparams dict (expects 'correction_patterns' key).
        """
        raw_patterns: List[str] = hyperparams.get("correction_patterns", [])
        self.patterns = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        self.semantic_threshold: float = hyperparams.get(
            "correction_semantic_threshold", 0.25
        )

        logger.info(
            "correction_detector_initialized",
            pattern_count=len(self.patterns),
            semantic_threshold=self.semantic_threshold,
        )

    def detect_from_text(self, user_message: str) -> CorrectionTier:
        """Detects corrections from user text using pattern matching.

        Args:
            user_message: The user's reply message.

        Returns:
            CorrectionTier.HARD if 2+ matches, SOFT if 1 match, NONE otherwise.
        """
        match_count = sum(
            1 for pattern in self.patterns if pattern.search(user_message)
        )

        if match_count >= 2:
            logger.info("correction_detected", tier="HARD", matches=match_count)
            return CorrectionTier.HARD
        elif match_count == 1:
            logger.info("correction_detected", tier="SOFT", matches=match_count)
            return CorrectionTier.SOFT
        else:
            return CorrectionTier.NONE

    def detect_semantic_contradiction(
        self,
        user_reply_embedding: np.ndarray,
        ai_response_embedding: np.ndarray,
    ) -> bool:
        """Detects semantic contradiction via cosine similarity.

        If the user's reply is semantically opposite to the AI's prior
        response (cosine similarity below threshold), it indicates a
        correction.

        Args:
            user_reply_embedding: 1-D embedding of the user's reply.
            ai_response_embedding: 1-D embedding of the AI's prior response.

        Returns:
            True if contradiction detected (similarity below threshold).
        """
        dot = np.dot(user_reply_embedding, ai_response_embedding)
        norm = (
            np.linalg.norm(user_reply_embedding)
            * np.linalg.norm(ai_response_embedding)
        )
        similarity = dot / (norm + 1e-9)

        is_contradiction = float(similarity) < self.semantic_threshold

        if is_contradiction:
            logger.info(
                "semantic_contradiction_detected",
                similarity=float(similarity),
                threshold=self.semantic_threshold,
            )

        return is_contradiction

    def detect(
        self,
        user_message: str,
        user_embedding: Optional[np.ndarray] = None,
        ai_embedding: Optional[np.ndarray] = None,
        thumbs_down: bool = False,
    ) -> CorrectionTier:
        """Combined detection: patterns + semantics + UI signal.

        Args:
            user_message: The user's reply text.
            user_embedding: Optional embedding of the user's reply.
            ai_embedding: Optional embedding of the AI's prior response.
            thumbs_down: Whether the user clicked the thumbs-down button.

        Returns:
            The highest-severity CorrectionTier detected.
        """
        # Thumbs-down is always HARD
        if thumbs_down:
            logger.info("correction_detected", tier="HARD", source="thumbs_down")
            return CorrectionTier.HARD

        # Pattern-based detection
        pattern_tier = self.detect_from_text(user_message)
        if pattern_tier == CorrectionTier.HARD:
            return CorrectionTier.HARD

        # Semantic contradiction check
        if user_embedding is not None and ai_embedding is not None:
            if self.detect_semantic_contradiction(user_embedding, ai_embedding):
                # Semantic contradiction escalates SOFT to HARD if patterns also matched
                if pattern_tier == CorrectionTier.SOFT:
                    return CorrectionTier.HARD
                return CorrectionTier.SOFT

        return pattern_tier
