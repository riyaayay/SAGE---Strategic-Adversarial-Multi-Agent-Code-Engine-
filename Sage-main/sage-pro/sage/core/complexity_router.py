import re
from typing import Dict, Any
import structlog

logger = structlog.get_logger(__name__)

OLLAMA_BASE = "http://localhost:11434/v1"

STRATEGIES = {
    "simple":   {"max_cycles":1,"epsilon":0.5,"architect_model":"codellama:34b","implementer_model":"codellama:34b","synthesizer_model":"codellama:34b","redteam_primary":"codellama:34b","redteam_secondary":"codellama:34b","base_url":OLLAMA_BASE},
    "medium":   {"max_cycles":2,"epsilon":0.15,"architect_model":"qwen2.5-coder:32b","implementer_model":"qwen2.5-coder:32b","synthesizer_model":"qwen2.5-coder:32b","redteam_primary":"qwen2.5-coder:32b","redteam_secondary":"qwen2.5-coder:32b","base_url":OLLAMA_BASE},
    "complex":  {"max_cycles":3,"epsilon":0.05,"architect_model":"deepseek-r1:32b","implementer_model":"qwen2.5-coder:32b","synthesizer_model":"qwen2.5-coder:32b","redteam_primary":"deepseek-r1:32b","redteam_secondary":"qwen2.5-coder:32b","base_url":OLLAMA_BASE},
    "boardroom":{"max_cycles":4,"epsilon":0.05,"architect_model":"qwen2.5:72b","implementer_model":"qwen2.5-coder:32b","synthesizer_model":"qwen2.5-coder:32b","redteam_primary":"qwen2.5:72b","redteam_secondary":"deepseek-r1:32b","base_url":OLLAMA_BASE},
}

BOARDROOM_RE = re.compile(r'\b(boardroom|full council|72b|debate this|use all models|critical system|mission critical|enterprise|production system)\b', re.I)
COMPLEX_RE = re.compile(r'\b(architect|system design|distributed|microservice|optimize|refactor|production|security|algorithm|vulnerability|scalab|audit)\b', re.I)
SIMPLE_RE = re.compile(r'\b(hi|hello|hey|thanks|what is|explain|define|who is|tell me|show me)\b', re.I)

def classify_complexity(query: str) -> str:
    q = query.lower().strip()
    wc = len(q.split())
    if BOARDROOM_RE.search(q): return "boardroom"
    if wc > 100 and len(COMPLEX_RE.findall(q)) >= 2: return "boardroom"
    if len(COMPLEX_RE.findall(q)) >= 2 or wc > 60: return "complex"
    if len(COMPLEX_RE.findall(q)) == 1 and wc > 25: return "complex"
    if wc <= 8 and SIMPLE_RE.search(q): return "simple"
    if wc <= 5: return "simple"
    return "medium"

def get_strategy(query: str) -> Dict[str, Any]:
    tier = classify_complexity(query)
    strategy = STRATEGIES[tier].copy()
    strategy["tier"] = tier
    logger.info("complexity_classified", tier=tier, query=query[:60], word_count=len(query.split()))
    return strategy
