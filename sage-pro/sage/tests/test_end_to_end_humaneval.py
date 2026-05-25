import pytest
from unittest.mock import AsyncMock, patch
from sage.core.graph import build_graph
from sage.core.types import ToolReport, SageRequest

@pytest.mark.asyncio
async def test_end_to_end_humaneval_mocked() -> None:
    """Asserts the full pipeline completes with clean reports using mocked agents."""
    
    graph = build_graph()
    
    # Mock all agent nodes to return canned responses
    with patch("sage.core.graph.architect_node", new=AsyncMock(return_value={"architect_spec": "spec"})):
        with patch("sage.core.graph.synthesize_node", new=AsyncMock(return_value={"final_code": "def correct(): pass", "divergence_index": 0.05})):
            with patch("sage.core.graph.crucible_node", new=AsyncMock(return_value={"cycle_history": [{}], "damage_trajectory": [0.01]})):
                
                req = SageRequest(task="def add(a, b):", max_cycles=3)
                state = {
                    "request": req,
                    "repo_files": [],
                    "xai_trace": []
                }
                
                result = await graph.ainvoke(state)
                
                assert "final_code" in result
                assert result["final_code"] == "def correct(): pass"
                assert 0.0 <= result["divergence_index"] <= 1.0
                assert len(result["damage_trajectory"]) >= 1
                assert "xai_trace" in result
