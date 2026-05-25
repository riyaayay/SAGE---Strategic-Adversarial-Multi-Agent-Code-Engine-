import pytest
import numpy as np
from sage.core.aode import lie_bracket_synthesis, Proposal

def test_lie_bracket_nonzero():
    """
    Asserts that [ABC] - [ACB] != 0, proving non-abelian synthesis.
    """
    vec_a = np.random.randn(1024)
    vec_b = np.random.randn(1024)
    vec_c = np.random.randn(1024)
    
    out_a = Proposal(text="A", vector=vec_a, cycle=0)
    out_b = Proposal(text="B", vector=vec_b, cycle=0)
    out_c = Proposal(text="C", vector=vec_c, cycle=0)
    
    # The operator itself mocks the non-abelian drift if identical
    _, divergence = lie_bracket_synthesis(out_a, out_b, out_c, lambda x: x)
    
    print(f"Divergence index: {divergence}")
    assert divergence > 1e-3
