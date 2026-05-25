import pytest
import numpy as np
from sage.core.aode import topological_route, torsion_warp, Proposal

def test_topological_route():
    query = np.random.randn(1024)
    corpus = np.random.randn(10, 1024)
    
    indices, (b1, b2) = topological_route(query, corpus, k=3)
    
    assert len(indices) == 3
    assert isinstance(b1, int)
    assert isinstance(b2, int)

def test_torsion_warp():
    baseline = np.array([1.0, 0.0, 0.0])
    anchor = np.array([0.0, 1.0, 0.0])
    
    warped = torsion_warp(baseline, anchor, alpha=1.0)
    
    # Warped should have a significant component perpendicular to anchor
    # and should be unit normalized
    assert np.isclose(np.linalg.norm(warped), 1.0)
    assert not np.array_equal(warped, baseline)

def test_proposal_dataclass():
    p = Proposal(text="test", vector=np.zeros(10), cycle=1)
    assert p.text == "test"
    assert p.damage == 1.0
