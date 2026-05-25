import numpy as np
import pytest
from sage.core.aode import (
    persistent_homology_features,
    torsion_perpendicular,
    lie_bracket_divergence,
    nash_damage
)

def test_persistent_homology_features_random_cloud() -> None:
    """Asserts that b0 >= 1 on a random point cloud."""
    points = np.random.randn(50, 16)
    features = persistent_homology_features(points)
    assert features["b0"] >= 1
    assert isinstance(features["voids"], list)

def test_torsion_perpendicular_orthogonal() -> None:
    """Asserts that the torsion nudge is orthogonal to the design vector."""
    design = np.array([1.0, 0.0, 0.0])
    basis = np.array([[0.0, 1.0, 0.0]])
    perp = torsion_perpendicular(design, basis)
    dot_product = np.dot(design, perp)
    assert abs(dot_product) < 1e-6

def test_torsion_perpendicular_unit_norm() -> None:
    """Asserts that the torsion nudge is a unit vector."""
    design = np.random.randn(1024)
    basis = np.random.randn(1, 1024)
    perp = torsion_perpendicular(design, basis)
    norm = np.linalg.norm(perp)
    assert abs(norm - 1.0) < 1e-6

def test_lie_bracket_divergence_identical_zero() -> None:
    """Asserts that identical code results in zero divergence."""
    code = "def main():\\n    print('hello')\\n"
    divergence = lie_bracket_divergence(code, code)
    assert divergence == 0.0

def test_lie_bracket_divergence_different_positive() -> None:
    """Asserts that different code results in positive divergence."""
    code_abc = "def add(a, b): return a + b"
    code_acb = "def sub(a, b): return a - b"
    divergence = lie_bracket_divergence(code_abc, code_acb)
    assert 0.0 < divergence <= 1.0

def test_nash_damage_monotonic() -> None:
    """Asserts that adding a violation increases the damage score."""
    report_clean = {"ruff": [], "mypy": []}
    report_dirty = {"ruff": ["E501"], "mypy": []}
    weights = {"ruff": 0.5, "mypy": 1.0}
    
    damage_clean = nash_damage(report_clean, weights)
    damage_dirty = nash_damage(report_dirty, weights)
    
    assert damage_dirty > damage_clean

def test_nash_damage_zero_clean() -> None:
    """Asserts that a clean report results in zero damage."""
    report = {"ruff": [], "mypy": [], "bandit": []}
    weights = {"ruff": 0.1, "mypy": 0.1, "bandit": 0.1}
    assert nash_damage(report, weights) == 0.0
