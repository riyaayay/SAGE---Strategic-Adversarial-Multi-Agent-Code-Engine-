import json
import structlog
from pathlib import Path
from typing import Any, Dict
from sage.core.types import XAITrace

logger = structlog.get_logger(__name__)

class TraceLogger:
    """Records reasoning traces to an append-only JSONL file for auditability."""

    def __init__(self, log_path: str = "logs/xai_trace.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_step(self, trace: XAITrace) -> None:
        """Appends a single XAI trace entry to the log file."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.dict(), default=str) + "\\n")
        except Exception as e:
            logger.error("xai_trace_write_failed", error=str(e))
