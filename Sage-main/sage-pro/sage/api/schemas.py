from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from sage.core.types import SageResponse

class CodeRequest(BaseModel):
    """Request schema for code generation."""
    task: str = Field(..., description="Natural language description of the coding task")
    context_files: List[str] = Field(default_factory=list)
    mode: Literal["fast", "deep", "long-context"] = "deep"
    priority: Literal["performance", "readability", "security"] = "performance"
    max_cycles: int = 5

class ReviewRequest(BaseModel):
    """Request schema for code review."""
    code: str
    spec: Optional[str] = None

class RefactorRequest(BaseModel):
    """Request schema for automated refactoring."""
    code: str
    target_pattern: str = "functional"

class SolveIssueRequest(BaseModel):
    """Request schema for solving a GitHub-style issue."""
    issue_description: str
    repo_snapshot: List[Dict[str, str]]

class APIResponse(SageResponse):
    """Standardized API response including SAGE-PRO metadata."""
    request_id: str
    status: str = "success"
