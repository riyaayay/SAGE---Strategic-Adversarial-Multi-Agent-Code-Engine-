import pytest
from unittest.mock import AsyncMock, MagicMock
from sage.core.crucible import crucible_loop
from sage.core.types import ToolReport

@pytest.mark.asyncio
async def test_crucible_stops_on_epsilon() -> None:
    """Asserts the loop stops when damage is below epsilon."""
    red_team = MagicMock()
    red_team.attack = AsyncMock(return_value={"tests": "", "security_findings": []})
    
    synthesizer = MagicMock()
    synthesizer.merge = AsyncMock(return_value="clean code")
    
    # Mock tool that returns clean report (0 damage)
    mock_tool = AsyncMock(return_value=ToolReport(tests_passed=True, total_damage=0.0))
    tools = {"ruff": AsyncMock(return_value=[]), "mypy": AsyncMock(return_value=[]), 
             "bandit": AsyncMock(return_value=[]), "sandbox": mock_tool}
    
    hyperparams = {"epsilon": 0.05, "max_cycles": 4}
    
    code, history, trajectory = await crucible_loop(
        "spec", "initial", red_team, synthesizer, tools, hyperparams
    )
    
    assert len(history) == 1
    assert trajectory[0] < 0.05

@pytest.mark.asyncio
async def test_crucible_stops_on_max_cycles() -> None:
    """Asserts the loop stops after max_cycles even if damage is high."""
    red_team = MagicMock()
    red_team.attack = AsyncMock(return_value={"tests": "", "security_findings": ["flaw"]})
    
    synthesizer = MagicMock()
    synthesizer.merge = AsyncMock(return_value="still dirty code")
    
    # Mock tool that returns high damage forever
    mock_tool = AsyncMock(return_value=ToolReport(tests_passed=False, total_damage=1.0))
    tools = {"ruff": AsyncMock(return_value=[{}]), "mypy": AsyncMock(return_value=[]), 
             "bandit": AsyncMock(return_value=[]), "sandbox": mock_tool}
    
    hyperparams = {"epsilon": 0.01, "max_cycles": 3}
    
    code, history, trajectory = await crucible_loop(
        "spec", "initial", red_team, synthesizer, tools, hyperparams
    )
    
    assert len(history) == 3
    assert len(trajectory) == 3

@pytest.mark.asyncio
async def test_crucible_records_full_trajectory() -> None:
    """Asserts the trajectory length matches the cycles run."""
    red_team = MagicMock()
    red_team.attack = AsyncMock(return_value={"tests": "", "security_findings": []})
    synthesizer = MagicMock()
    synthesizer.merge = AsyncMock(return_value="code")
    
    tools = {"ruff": AsyncMock(return_value=[]), "mypy": AsyncMock(return_value=[]), 
             "bandit": AsyncMock(return_value=[]), "sandbox": AsyncMock(return_value=ToolReport())}
    
    hyperparams = {"epsilon": 0.001, "max_cycles": 2}
    
    _, history, trajectory = await crucible_loop(
        "spec", "initial", red_team, synthesizer, tools, hyperparams
    )
    
    assert len(trajectory) == len(history)
