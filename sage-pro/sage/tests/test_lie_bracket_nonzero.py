import ast
import pytest
from hypothesis import given, strategies as st
from sage.core.aode import lie_bracket_divergence

@given(
    code_a=st.text(min_size=1, alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=("\\0",))),
    code_b=st.text(min_size=1, alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=("\\0",)))
)
def test_lie_bracket_divergence_properties(code_a: str, code_b: str) -> None:
    """Property test for Lie Bracket divergence.
    
    Verifies that:
    1. Divergence is always between [0, 1].
    2. Divergence is 0 if and only if AST is equal.
    """
    # Filter for valid Python snippets to avoid parse errors in the operator
    try:
        ast.parse(code_a)
        ast.parse(code_b)
    except Exception:
        # Ignore non-parseable random text for this property
        return

    div = lie_bracket_divergence(code_a, code_b)
    
    assert 0.0 <= div <= 1.0
    
    # Check AST equality
    dump_a = ast.dump(ast.parse(code_a))
    dump_b = ast.dump(ast.parse(code_b))
    
    if dump_a == dump_b:
        assert div == 0.0
    else:
        assert div > 0.0
