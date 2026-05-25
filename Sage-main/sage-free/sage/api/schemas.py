from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class AODERequest(BaseModel):
    query: str

class AODEResponse(BaseModel):
    final_answer: str
    divergence_index: float
    nash_cycles: int
    xai_trace: List[str]
    vram_peak_gb: float
    cycle_history: Optional[List[Dict[str, Any]]] = None
