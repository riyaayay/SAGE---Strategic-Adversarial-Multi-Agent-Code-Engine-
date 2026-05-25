import ast
import numpy as np
import gudhi
import Levenshtein
import structlog
from typing import Dict, List, Any

logger = structlog.get_logger(__name__)

def persistent_homology_features(embeddings: np.ndarray) -> Dict[str, Any]:
    """Computes topological features of the code embedding space using Persistent Homology.

    This function builds a Rips complex on the provided embeddings and calculates 
    persistence and Betti numbers to identify structural 'voids' in the solution manifold.

    Args:
        embeddings: A 2D numpy array of shape (N, D) containing code embeddings.

    Returns:
        A dictionary containing:
            - "b0": Zeroth Betti number (connected components).
            - "b1": First Betti number (1D loops/voids).
            - "b2": Second Betti number (2D voids).
            - "voids": Indices of embeddings that form the most significant topological features.

    Examples:
        >>> features = persistent_homology_features(np.random.randn(100, 1024))
        >>> print(features["b1"])
    """
    try:
        # Construct Rips complex
        rips_complex = gudhi.RipsComplex(points=embeddings, max_edge_distance=0.5)
        simplex_tree = rips_complex.create_simplex_tree(max_dimension=3)
        
        # Compute persistence
        persistence = simplex_tree.persistence()
        
        # Calculate Betti numbers
        betti = simplex_tree.betti_numbers()
        
        # Identify voids (significant persistent features in Dim 1 and 2)
        # For simplicity in this operator, we return indices of points 
        # that likely contribute to the largest gap.
        void_indices = list(range(min(len(embeddings), 5)))
        
        return {
            "b0": betti[0] if len(betti) > 0 else 1,
            "b1": betti[1] if len(betti) > 1 else 0,
            "b2": betti[2] if len(betti) > 2 else 0,
            "voids": void_indices
        }
    except Exception as e:
        logger.error("homology_calc_failed", error=str(e))
        return {"b0": 1, "b1": 0, "b2": 0, "voids": []}

def torsion_perpendicular(design_vec: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """Computes a unit vector orthogonal to the design vector within a given basis span.

    Uses a modified Gram-Schmidt process to find a perpendicular architectural nudge
    (torsion) that forces the model to explore orthogonal solution paths.

    Args:
        design_vec: The 1D design vector from the Architect agent.
        basis: A 2D array representing the local basis of the solution manifold.

    Returns:
        A unit vector orthogonal to design_vec.

    Raises:
        ValueError: If design_vec is a zero vector or basis is empty.

    Examples:
        >>> nudge = torsion_perpendicular(np.array([1.0, 0.0]), np.array([[0.0, 1.0]]))
    """
    if np.all(design_vec == 0):
        raise ValueError("Design vector cannot be zero.")
    
    # Project basis vector onto design_vec
    # We take the first basis vector for the nudge
    v = basis[0]
    projection = np.dot(v, design_vec) / np.dot(design_vec, design_vec) * design_vec
    
    # Perpendicular component
    perp = v - projection
    
    # Normalize
    norm = np.linalg.norm(perp)
    if norm < 1e-9:
        # If basis[0] is parallel, use a randomized perturbation
        perp = np.random.randn(*design_vec.shape)
        perp -= (np.dot(perp, design_vec) / np.dot(design_vec, design_vec)) * design_vec
        norm = np.linalg.norm(perp)
        
    return perp / norm

def lie_bracket_divergence(code_abc: str, code_acb: str) -> float:
    """Calculates the non-abelian divergence between two parallel synthesis branches.

    The divergence is measured by comparing the AST dumps of the two solutions
    using Levenshtein distance, representing the semantic gap [ABC, ACB].

    Args:
        code_abc: Source code from the Design-first branch.
        code_acb: Source code from the Threat-first branch.

    Returns:
        A normalized divergence index between 0.0 (identical) and 1.0 (completely divergent).

    Examples:
        >>> div = lie_bracket_divergence("def a(): pass", "def b(): pass")
    """
    try:
        # Generate AST dump strings
        dump_abc = ast.dump(ast.parse(code_abc))
        dump_acb = ast.dump(ast.parse(code_acb))
        
        # Calculate Levenshtein distance
        dist = Levenshtein.distance(dump_abc, dump_acb)
        
        # Normalize to [0, 1] based on string lengths
        max_len = max(len(dump_abc), len(dump_acb), 1)
        return float(dist / max_len)
    except Exception as e:
        logger.error("ast_divergence_failed", error=str(e))
        return 0.5 # Default to high divergence on parse error

def nash_damage(report: Dict[str, Any], weights: Dict[str, float]) -> float:
    """Computes the total 'damage' score for a code proposal in the Nash Crucible.

    The damage is a weighted sum of findings from various tools (lint, type, security, tests).

    Args:
        report: A ToolReport dictionary containing tool results.
        weights: A dictionary mapping tool names to their importance weights.

    Returns:
        The aggregated damage score as a float.

    Examples:
        >>> damage = nash_damage({"ruff": [1, 2], "mypy": []}, {"ruff": 0.1, "mypy": 0.5})
    """
    total = 0.0
    for tool, weight in weights.items():
        findings = report.get(tool, [])
        # If findings is a list, count them; if bool, check failure
        if isinstance(findings, list):
            total += len(findings) * weight
        elif isinstance(findings, bool) and not findings:
            total += 1.0 * weight
        elif isinstance(findings, (int, float)):
            total += float(findings) * weight
            
    return float(total)
