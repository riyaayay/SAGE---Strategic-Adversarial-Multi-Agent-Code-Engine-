import structlog
import re
from typing import Dict, Any
from sage.tools.sandbox import run_in_sandbox

logger = structlog.get_logger(__name__)

def generate_hypothesis_strategy(signature: str) -> str:
    """Generates a Hypothesis @given strategy based on a function signature.

    Args:
        signature: The function signature string (e.g. "def process(data: list[int]) -> bool").

    Returns:
        A string representing the @given(...) decorator.
    """
    # Simple type to strategy map
    type_map = {
        "int": "st.integers()",
        "float": "st.floats(allow_nan=False, allow_infinity=False)",
        "str": "st.text()",
        "bool": "st.booleans()",
        "list": "st.lists({})",
        "dict": "st.dictionaries(st.text(), st.text())"
    }
    
    # Extract arguments using regex
    # Simplified: looks for name: type
    args = re.findall(r"(\w+):\s*([\w\[\]]+)", signature)
    strategies = []
    
    for name, type_hint in args:
        # Handle list[T]
        list_match = re.match(r"list\[(\w+)\]", type_hint)
        if list_match:
            inner_type = list_match.group(1)
            inner_strategy = type_map.get(inner_type, "st.text()")
            strategies.append(f"{name}={type_map['list'].format(inner_strategy)}")
        else:
            strategies.append(f"{name}={type_map.get(type_hint, 'st.text()')}")
            
    return f"@given({', '.join(strategies)})"

async def run_property_tests(code: str, strategy: str) -> Dict[str, Any]:
    """Executes property-based tests in the sandbox.

    Args:
        code: The Python code to test.
        strategy: The Hypothesis strategy decorator string.

    Returns:
        A dictionary containing the results of the property tests.
    """
    # Wrap the code in a hypothesis test function
    # We assume the first function in 'code' is the one to test.
    match = re.search(r"def (\w+)\(", code)
    func_name = match.group(1) if match else "unknown"
    
    test_code = f"""
from hypothesis import given, strategies as st

{strategy}
def test_property_of_{func_name}(**kwargs):
    result = {func_name}(**kwargs)
    # Generic assertion: shouldn't crash
    assert True
"""
    report = await run_in_sandbox(code, test_code)
    return {
        "passed": report.tests_passed,
        "coverage": report.coverage
    }
