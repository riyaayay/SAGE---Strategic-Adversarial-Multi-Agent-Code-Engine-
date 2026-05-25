from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ToolReport(BaseModel):
    """Aggregated findings from the mechanical grounding tools."""
    ruff: List[Dict[str, Any]] = Field(default_factory=list)
    mypy: List[Dict[str, Any]] = Field(default_factory=list)
    bandit: List[Dict[str, Any]] = Field(default_factory=list)
    semgrep: List[Dict[str, Any]] = Field(default_factory=list)
    tests_passed: bool = True
    coverage: float = 0.0
    cyclomatic_complexity: float = 0.0
    total_damage: float = 0.0

    class Config:
        frozen = True

class AgentResponse(BaseModel):
    """Standardized response from a SAGE specialist agent."""
    agent_name: str
    content: str
    code: Optional[str] = None
    thought_trace: List[str] = Field(default_factory=list)
    vram_usage_gb: float = 0.0
    latency_ms: float = 0.0

    class Config:
        frozen = True

class CrucibleCycle(BaseModel):
    """Metadata for a single iteration of the Nash refinement loop."""
    cycle_index: int
    damage_score: float
    findings: ToolReport
    refinement_prompt: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = True

class XAITrace(BaseModel):
    """Explainable AI trace for the AODE reasoning process."""
    step_name: str
    operator: str
    divergence_signal: float
    action_taken: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = True

class SageRequest(BaseModel):
    """External request to the SAGE-PRO engine."""
    task: str
    context_files: List[str] = Field(default_factory=list)
    max_cycles: int = 5
    priority: str = "performance"

class SageResponse(BaseModel):
    """Final output from the SAGE-PRO engine."""
    final_code: str
    final_tests: str
    divergence_index: float
    nash_cycles: int
    damage_trajectory: List[float]
    vram_peak_gb: float
    xai_trace: List[XAITrace]
    execution_time_sec: float
