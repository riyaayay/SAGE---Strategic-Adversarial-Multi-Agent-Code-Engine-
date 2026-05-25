"""
SAGE-PRO Semantic Torsion Module
════════════════════════════════
Implements the Torsion Tensor T^λ_{μν} ≠ 0 to warp the generative path
away from the baseline geodesic.

Two levels of enforcement:
  1. Prompt-level: Orthogonal suffix selected via min|cos(θ)| (Gram-Schmidt)
  2. Logit-level: Token ID penalties applied via vLLM logit_bias field

    P(token | context) = softmax(logits − Penalty(token ∈ Baseline_Tokens))
"""

import numpy as np
import structlog
from typing import Dict, Tuple, Any

logger = structlog.get_logger(__name__)


# TORSION_PENALTY_MAP is now injected via hyperparams.


def torsion_to_logit_bias(torsion_label: str, penalty_map: Dict[str, Dict[int, float]]) -> Dict[int, float]:
    """Converts a torsion axis label to a vLLM logit_bias dict.

    Args:
        torsion_label: One of the 7 axis labels from TORSION_PENALTY_MAP.

    Returns:
        A dict mapping token IDs (int) to penalty floats (negative).
        Returns empty dict if the label is not recognized.
    """
    bias = penalty_map.get(torsion_label, {})
    if not bias:
        logger.warning("torsion_label_not_found", label=torsion_label)
    return dict(bias)


def compute_torsion_suffix(
    design_text: str,
    embedder: Any,
    suffix_library: Dict[str, str],
    penalty_map: Dict[str, Dict[int, float]],
) -> Tuple[str, Dict[int, float]]:
    """Picks the torsion suffix most perpendicular to the current design
    AND generates the corresponding logit_bias for token-level enforcement.

    Uses cosine similarity to identify the nudge that provides the
    highest divergence (orthogonal projection) from the baseline manifold.

    Args:
        design_text: The architectural design text from the Architect.
        embedder: The SentenceTransformer model.
        suffix_library: A mapping of nudge labels to their markdown text.

    Returns:
        A tuple of (suffix_text, logit_bias_dict):
            - suffix_text: The selected torsion suffix string for prompt injection.
            - logit_bias_dict: Token penalties for vLLM logit_bias enforcement.
    """
    design_vec = embedder.encode([design_text], convert_to_numpy=True)[0]

    suffixes = list(suffix_library.values())
    labels = list(suffix_library.keys())

    suffix_vecs = embedder.encode(suffixes, convert_to_numpy=True)

    # Calculate cosine similarity
    # Perpendicular means similarity close to 0
    dot_products = np.dot(suffix_vecs, design_vec)
    norms = np.linalg.norm(suffix_vecs, axis=1) * np.linalg.norm(design_vec)
    similarities = dot_products / (norms + 1e-9)

    # We want the one closest to 0 (most orthogonal)
    ortho_scores = np.abs(similarities)
    best_idx = np.argmin(ortho_scores)

    selected_label = labels[best_idx]
    logit_bias = torsion_to_logit_bias(selected_label, penalty_map)

    logger.info(
        "torsion_suffix_selected",
        label=selected_label,
        ortho_score=float(ortho_scores[best_idx]),
        logit_bias_count=len(logit_bias),
    )

    return suffixes[best_idx], logit_bias
