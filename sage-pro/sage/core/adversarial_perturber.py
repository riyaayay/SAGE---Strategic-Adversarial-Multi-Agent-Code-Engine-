"""
SAGE-PRO Novel System 3: Adversarial Latent Perturbation
══════════════════════════════════════════════════════════
Wires the Red Team directly into the FAISS manifold.

Instead of attacking code with prompt-based heuristics alone,
this system MATHEMATICALLY PERTURBS the embedding vector of the
current task to find the nearest "High Penalty Centroid" in the
routing ledger, then forces the Implementer to prove its code
survives the conditions that caused the failure there.

Algorithm:
    1. Embed the current task → q_vec
    2. Find K nearest centroids in the penalty-weighted manifold
    3. For each high-penalty centroid:
       - Compute perturbation: delta = alpha * (penalty_centroid - q_vec)
       - Perturbed query: q_perturbed = q_vec + delta
       - Retrieve the representative failure queries from that centroid
    4. Feed the perturbed context to the Red Team as attack vectors
    5. Score: how much does the solution degrade under perturbation?

Config: aode_hyperparams.yaml → adversarial_perturbation
"""

import numpy as np
import structlog
from typing import Dict, Any, List, Tuple, Optional

logger = structlog.get_logger(__name__)


class AdversarialLatentPerturber:
    """Generates adversarial attack vectors by perturbing through
    the FAISS manifold toward known failure regions."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes from config.

        Args:
            hyperparams: Full hyperparams dict.
        """
        cfg = hyperparams.get("adversarial_perturbation", {})
        self.perturbation_alpha: float = cfg.get("alpha", 0.3)
        self.num_perturbations: int = cfg.get("num_perturbations", 3)
        self.penalty_threshold: float = cfg.get("penalty_threshold", -0.2)
        self.noise_stddev: float = cfg.get("noise_stddev", 0.05)

        logger.info(
            "adversarial_perturber_init",
            alpha=self.perturbation_alpha,
            num_perturbations=self.num_perturbations,
        )

    def find_high_penalty_centroids(
        self,
        q_table: Dict[Tuple[int, int], float],
        centroids: np.ndarray,
        num_actions: int,
    ) -> List[Tuple[int, float, np.ndarray]]:
        """Finds centroids where agents have consistently negative Q-values.

        Args:
            q_table: CTR engine Q-table.
            centroids: FAISS centroid matrix (n_clusters × dims).
            num_actions: Number of agent actions.

        Returns:
            List of (cluster_id, mean_q, centroid_vector) for high-penalty clusters.
        """
        from collections import defaultdict
        cluster_q: Dict[int, List[float]] = defaultdict(list)

        for (cid, action), q_val in q_table.items():
            cluster_q[cid].append(q_val)

        penalty_centroids = []
        for cid, q_vals in cluster_q.items():
            mean_q = np.mean(q_vals)
            if mean_q < self.penalty_threshold and cid < len(centroids):
                penalty_centroids.append((cid, float(mean_q), centroids[cid]))

        # Sort by worst (most negative) Q-value
        penalty_centroids.sort(key=lambda x: x[1])
        return penalty_centroids[:self.num_perturbations * 2]

    def generate_perturbations(
        self,
        query_embedding: np.ndarray,
        penalty_centroids: List[Tuple[int, float, np.ndarray]],
    ) -> List[Dict[str, Any]]:
        """Generates adversarial perturbation vectors.

        For each high-penalty centroid, computes a perturbation that
        shifts the query embedding TOWARD the failure region, creating
        an adversarial test case.

        Args:
            query_embedding: The original task embedding.
            penalty_centroids: From find_high_penalty_centroids().

        Returns:
            List of perturbation dicts with:
              - perturbed_vec: the shifted embedding
              - source_cluster: which failure cluster it points toward
              - perturbation_magnitude: how far we shifted
              - attack_label: human-readable attack description
        """
        perturbations = []

        for cid, mean_q, centroid in penalty_centroids[:self.num_perturbations]:
            # Direction from query toward the failure centroid
            direction = centroid - query_embedding
            dist = np.linalg.norm(direction)

            if dist < 1e-8:
                continue

            # Normalize direction
            direction_unit = direction / dist

            # Apply perturbation: shift alpha fraction toward failure
            delta = self.perturbation_alpha * direction
            perturbed = query_embedding + delta

            # Add small Gaussian noise for diversity
            noise = np.random.normal(0, self.noise_stddev, size=perturbed.shape)
            perturbed = perturbed + noise

            # L2 normalize the perturbed vector
            norm = np.linalg.norm(perturbed)
            if norm > 0:
                perturbed = perturbed / norm

            perturbation_mag = float(np.linalg.norm(delta))

            perturbations.append({
                "perturbed_vec": perturbed,
                "source_cluster": cid,
                "source_mean_q": mean_q,
                "perturbation_magnitude": perturbation_mag,
                "direction_cosine": float(
                    np.dot(query_embedding, centroid)
                    / (np.linalg.norm(query_embedding) * np.linalg.norm(centroid) + 1e-8)
                ),
                "attack_label": (
                    f"Latent Perturbation toward failure cluster {cid} "
                    f"(mean_q={mean_q:.3f}, shift={perturbation_mag:.4f})"
                ),
            })

        logger.info(
            "perturbations_generated",
            count=len(perturbations),
            target_clusters=[p["source_cluster"] for p in perturbations],
        )
        return perturbations

    def build_adversarial_context(
        self,
        perturbations: List[Dict[str, Any]],
        cluster_queries: Dict[int, List[str]],
    ) -> str:
        """Builds a text context for the Red Team from perturbation results.

        Translates the mathematical perturbations into natural language
        attack instructions for the Red Team agent.

        Args:
            perturbations: From generate_perturbations().
            cluster_queries: Representative queries per cluster.

        Returns:
            Attack context string for the Red Team prompt.
        """
        if not perturbations:
            return ""

        lines = [
            "# Adversarial Latent Perturbation Report",
            "The following attack vectors were generated by mathematically",
            "perturbing the current query toward known failure regions",
            "in the FAISS manifold.\n",
        ]

        for i, p in enumerate(perturbations, 1):
            cid = p["source_cluster"]
            queries = cluster_queries.get(cid, [])
            query_block = "\n".join(f"    - {q[:100]}" for q in queries[-3:])

            lines.append(f"## Attack Vector {i}: {p['attack_label']}")
            lines.append(f"  Perturbation magnitude: {p['perturbation_magnitude']:.4f}")
            lines.append(f"  Direction cosine similarity: {p['direction_cosine']:.4f}")
            lines.append(f"  Failure cluster mean Q-value: {p['source_mean_q']:.3f}")

            if query_block:
                lines.append(f"  Queries that FAILED in this region:")
                lines.append(query_block)

            lines.append(f"  → PROVE the current solution survives these conditions.\n")

        return "\n".join(lines)
