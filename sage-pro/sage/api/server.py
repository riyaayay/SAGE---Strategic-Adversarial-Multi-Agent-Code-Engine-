"""
SAGE-PRO FastAPI Server
═══════════════════════
Headless API for the Axiomatic Orthogonal Divergence Engine.
Bootstraps all agents, tools, and the LangGraph pipeline on startup.
"""

import os
import uvicorn
import yaml
import structlog
import uuid
import time
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sage.api.schemas import CodeRequest, ReviewRequest, RefactorRequest, SolveIssueRequest, APIResponse
from sage.api.streaming import create_streaming_response
from sage.api.stream_endpoint import router as stream_router
from sage.api.auth_routes import router as auth_router
from sage.api.chat_routes import router as chat_router
from sage.api.orchestrator_routes import router as orchestrator_router
from sage.api.feature_routes import router as feature_router
from sage.core.graph import build_graph
from sage.core.types import SageRequest

# Agent imports
from sage.agents.architect import Architect
from sage.agents.implementer import Implementer
from sage.agents.red_team import RedTeam
from sage.agents.synthesizer import Synthesizer
from sage.core.routing import CodeTopologyRouter

# Tool imports
from sage.tools.sandbox import run_in_sandbox, run_command_in_sandbox
from sage.tools.linter import run_ruff
from sage.tools.security import run_bandit, run_semgrep

logger = structlog.get_logger(__name__)

app = FastAPI(title="SAGE-PRO Engine API", version="3.0.0")

# Register routers
app.include_router(stream_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(orchestrator_router)
app.include_router(feature_router)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────
#  Bootstrap agents & tools at module level
# ─────────────────────────────────────────────────────────────────────

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _build_agents(hyperparams: dict) -> dict:
    """Instantiate all 4 agents + router from environment config."""
    from sage.core.udrk_kernel import build_udrk_system_prompt
    
    vllm_hosts = hyperparams.get("vllm_hosts", {})
    agent_configs = hyperparams.get("agents", {})
    
    arch_cfg = agent_configs.get("architect", {})
    impl_cfg = agent_configs.get("implementer", {})
    syn_cfg = agent_configs.get("synthesizer", {})
    rt_cfg = agent_configs.get("redteam", {})

    return {
        "architect": Architect(
            base_url=_env("VLLM_HOST_ARCHITECT", vllm_hosts.get("architect", "http://localhost:8001/v1")),
            model_name=arch_cfg.get("model_name", "qwen2.5:72b"),
            prompt_path=arch_cfg.get("prompt_path", "sage/prompts/architect.md"),
            temperature=arch_cfg.get("temperature", 0.3),
            udrk_prompt=build_udrk_system_prompt("architect", hyperparams),
        ),
        "implementer": Implementer(
            base_url=_env("VLLM_HOST_IMPLEMENTER", vllm_hosts.get("implementer", "http://localhost:8002/v1")),
            model_name=impl_cfg.get("model_name", "qwen2.5-coder:32b"),
            prompt_path=impl_cfg.get("prompt_path", "sage/prompts/implementer.md"),
            temperature=impl_cfg.get("temperature", 0.1),
            udrk_prompt=build_udrk_system_prompt("implementer", hyperparams),
        ),
        "synthesizer": Synthesizer(
            base_url=_env("VLLM_HOST_SYNTHESIZER", vllm_hosts.get("synthesizer", "http://localhost:8003/v1")),
            model_name=syn_cfg.get("model_name", "codellama:34b"),
            prompt_path=syn_cfg.get("prompt_path", "sage/prompts/synthesizer.md"),
            temperature=syn_cfg.get("temperature", 0.0),
            udrk_prompt=build_udrk_system_prompt("synthesizer", hyperparams),
        ),
        "red_team": RedTeam(
            base_url=_env("VLLM_HOST_REDTEAM", vllm_hosts.get("redteam", "http://localhost:8004/v1")),
            primary_model=rt_cfg.get("primary_model", "deepseek-coder-v2:16b"),
            secondary_model=rt_cfg.get("secondary_model", "deepseek-r1:32b"),
            primary_temperature=rt_cfg.get("primary_temperature", 0.7),
            secondary_temperature=rt_cfg.get("secondary_temperature", 0.5),
            prompt_path=rt_cfg.get("prompt_path", "sage/prompts/red_team.md"),
            udrk_prompt=build_udrk_system_prompt("red_team", hyperparams),
        ),
        "router": CodeTopologyRouter(
            model_name=hyperparams.get("embedding_model", "BAAI/bge-small-en-v1.5"),
            index_dims=hyperparams.get("index_dims", 384),
            max_neighbors=hyperparams.get("routing_max_neighbors", 5),
            search_cap=hyperparams.get("routing_search_cap", 500),
        ),
    }


def _build_tools() -> dict:
    """Build tool callables compatible with the Crucible loop."""
    import tempfile
    from pathlib import Path

    async def ruff_tool(code: str):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            return await run_ruff(f.name)

    async def mypy_tool(code: str):
        """Run mypy via sandbox — returns findings list."""
        import json as _json
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            ret, stdout, stderr = await run_command_in_sandbox(
                ["python3", "-m", "mypy", "--no-error-summary", "--output", "json", f.name]
            )
            try:
                return _json.loads(stdout) if stdout else []
            except Exception:
                return []

    async def bandit_tool(code: str):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            return await run_bandit(f.name)

    async def sandbox_tool(code: str, tests: str):
        return await run_in_sandbox(code, tests)

    return {
        "ruff": ruff_tool,
        "mypy": mypy_tool,
        "bandit": bandit_tool,
        "sandbox": sandbox_tool,
    }


def _load_hyperparams() -> dict:
    """Load AODE hyperparameters from YAML config."""
    config_path = "configs/aode_hyperparams.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("hyperparams_not_found", path=config_path)
        return {
            "epsilon": 0.05,
            "delta": 0.02,
            "max_cycles": 4,
            "damage_weights": {
                "ruff": 0.1, "mypy": 0.2, "bandit": 0.5,
                "semgrep": 0.4, "tests": 1.0, "complexity": 0.05,
            },
        }


def _load_torsion_penalties() -> dict:
    """Load torsion token penalty map from YAML config."""
    config_path = "configs/torsion_penalties.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("torsion_penalties_not_found", path=config_path)
        return {}


# Lazy-initialized globals — created on first request
_agents = None
_tools = None
_hyperparams = None
_torsion_penalties = None
_v2_subsystems = None
_compiled_graph = None


def _bootstrap_v2(hyperparams: dict) -> dict:
    """Bootstraps all SAGE-PRO v2 subsystems from config."""
    from sage.core.ctr_engine import CTREngine
    from sage.core.manifold_mutator import ManifoldMutator
    from sage.core.agent_penalty_system import AgentPenaltySystem
    from sage.core.correction_detector import CorrectionDetector
    from sage.core.reward_crystallizer import RewardCrystallizer
    from sage.core.routing_ledger import RoutingLedger

    # Novel Systems
    from sage.core.agent_spawner import DynamicAgentSpawner
    from sage.core.execution_trace_embedder import ExecutionTraceEmbedder
    from sage.core.adversarial_perturber import AdversarialLatentPerturber
    from sage.core.ast_diff_reward import ASTDiffRewardCrystallizer
    from sage.core.skill_distiller import SkillDistiller
    from sage.core.chaos_curriculum import ChaosCurriculumEngine

    subsystems = {
        "ctr_engine": CTREngine(hyperparams),
        "manifold_mutator": ManifoldMutator(hyperparams),
        "penalty_system": AgentPenaltySystem(hyperparams),
        "correction_detector": CorrectionDetector(hyperparams),
        "reward_crystallizer": RewardCrystallizer(hyperparams),
        "routing_ledger": RoutingLedger(),
        # Novel v2 systems
        "agent_spawner": DynamicAgentSpawner(hyperparams),
        "execution_trace_embedder": ExecutionTraceEmbedder(hyperparams),
        "adversarial_perturber": AdversarialLatentPerturber(hyperparams),
        "ast_diff_reward": ASTDiffRewardCrystallizer(hyperparams),
        "skill_distiller": SkillDistiller(hyperparams),
        "chaos_curriculum": ChaosCurriculumEngine(hyperparams),
    }

    # Mistake Library requires ChromaDB — only init if CHROMA_PATH is set
    chroma_path = os.environ.get("CHROMA_PATH", "data/chroma")
    ml_cfg = hyperparams.get("mistake_library", {})
    try:
        from sage.memory.mistake_library import MistakeLibrary
        subsystems["mistake_library"] = MistakeLibrary(
            chroma_path=chroma_path,
            collection_name=ml_cfg.get("collection_name", "mistake_library"),
            top_k=ml_cfg.get("top_k", 3),
        )
    except Exception as e:
        logger.warning("mistake_library_init_failed", error=str(e))
        subsystems["mistake_library"] = None

    # Load Q-table from disk if available
    subsystems["ctr_engine"].load()  # type: ignore

    logger.info("v2_subsystems_bootstrapped", components=list(subsystems.keys()))
    return subsystems


def _get_v2_subsystems() -> dict:
    """Returns the bootstrapped v2 subsystems (public for chat_routes)."""
    global _v2_subsystems, _hyperparams
    if _v2_subsystems is None:
        if _hyperparams is None:
            _hyperparams = _load_hyperparams()
        _v2_subsystems = _bootstrap_v2(_hyperparams)
    return _v2_subsystems


def _get_graph():
    """Returns a compiled graph with live agents and tools.

    The compiled graph (including its MemorySaver checkpointer) is
    cached as a module-level global so that checkpoint state persists
    across requests.  This is CRITICAL for the Human-in-the-Loop
    interrupt_after pattern — if we rebuilt the graph on every call,
    the MemorySaver would be fresh and all checkpoint state lost.
    """
    global _agents, _tools, _hyperparams, _torsion_penalties, _v2_subsystems, _compiled_graph
    if _compiled_graph is None:
        _hyperparams = _load_hyperparams()
        _agents = _build_agents(_hyperparams)
        _tools = _build_tools()
        _torsion_penalties = _load_torsion_penalties()
        _v2_subsystems = _bootstrap_v2(_hyperparams)
        _compiled_graph = build_graph(_agents, _tools, _hyperparams, _torsion_penalties)
        logger.info("sage_pipeline_bootstrapped",
                     agents=list(_agents.keys()),
                     tools=list(_tools.keys()),
                     v2=list(_v2_subsystems.keys()))
    return _compiled_graph


# ─────────────────────────────────────────────────────────────────────
#  HTTP middleware
# ─────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id_and_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info("http_request", path=request.url.path, duration=duration, status_code=response.status_code)
    response.headers["X-Request-ID"] = request_id
    return response


# ─────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """SAGE-PRO API root — headless engine, no frontend."""
    return {
        "service": "SAGE-PRO Engine",
        "version": "3.0.0",
        "aode": True,
        "features": [
            "live_rendering", "vision_debugging", "time_travel",
            "lsp_bridge", "chaos_dreamer",
        ],
        "endpoints": [
            "/v1/code", "/v1/sage/stream", "/v1/review", "/v1/correction",
            "/v1/history", "/auth/google", "/auth/me", "/healthz", "/readyz",
            "/v1/preview/render", "/v1/vision/debug", "/v1/timeline/{thread_id}",
            "/v1/lsp/references", "/v1/lsp/definition", "/v1/lsp/rename",
            "/v1/dreamer/dream", "/v1/dreamer/start", "/v1/dreamer/stats",
        ],
    }


@app.post("/v1/code", response_model=APIResponse)
async def generate_code(req: CodeRequest):
    """Generates adversarially-hardened code for a given task.
    
    v2 enhancement: Retrieves past mistakes from the Mistake Library
    and injects them as hidden context before running the pipeline.
    """
    graph = _get_graph()
    
    # ── v2: Retrieve past mistakes and inject as context ──
    subsystems = _get_v2_subsystems()
    mistake_context = ""
    ml = subsystems.get("mistake_library")
    if ml is not None:
        try:
            from sage.core.udrk_kernel import build_mistake_context
            mistakes = ml.retrieve(query_text=req.task)
            mistake_context = build_mistake_context(mistakes)
        except Exception as e:
            logger.warning("mistake_retrieval_failed", error=str(e))

    # Prepend mistake context to the task if available
    enriched_task = req.task
    if mistake_context:
        enriched_task = f"{mistake_context}\n\n---\n\n{req.task}"
        logger.info("mistake_context_injected", mistakes_found=len(mistake_context.split("\n")))

    sage_req = SageRequest(
        task=enriched_task,
        context_files=req.context_files,
        max_cycles=req.max_cycles,
        priority=req.priority,
    )

    try:
        result = await graph.ainvoke({"request": sage_req, "repo_files": []})
        
        # ── v2: Log to routing ledger for daily batch processing ──
        ledger = subsystems["routing_ledger"]
        ledger.log(
            user_id="anonymous",  # In production, extract from JWT
            query_hash=str(hash(req.task)),
            cluster_id=0,  # In production, from CTR engine
            action_idx=0,
            agent_sequence=["architect", "implementer", "red_team", "synthesizer"],
        )
        
        return APIResponse(
            request_id=str(uuid.uuid4()),
            **result,
        )
    except Exception as e:
        logger.error("graph_invocation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/review")
async def review_code(req: ReviewRequest):
    """Performs a Red-Team review of existing code."""
    return {"status": "under_construction"}


@app.get("/healthz")
async def health_check():
    """Checks if the SAGE-PRO server is alive."""
    return {"status": "healthy"}


@app.get("/readyz")
async def readiness_check():
    """Checks if all co-resident vLLM backends are reachable."""
    global _hyperparams
    if _hyperparams is None:
        _hyperparams = _load_hyperparams()
        
    vllm_hosts = _hyperparams.get("vllm_hosts", {})
    hosts = list(vllm_hosts.values())
    
    if not hosts:
        hosts = [
            "http://localhost:8001/v1",
            "http://localhost:8002/v1",
            "http://localhost:8003/v1",
            "http://localhost:8004/v1"
        ]
        
    async with httpx.AsyncClient() as client:
        for host in hosts:
            # We want to ping the base URL's /models endpoint
            url = f"{host.rstrip('/')}/models"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise HTTPException(status_code=503, detail=f"vLLM host {host} not ready")
            except Exception:
                raise HTTPException(status_code=503, detail=f"vLLM host {host} unreachable")
    return {"status": "all_systems_ready"}


if __name__ == "__main__":
    hyperparams = _load_hyperparams()
    host = hyperparams.get("server_host", "0.0.0.0")
    port = hyperparams.get("server_port", 8000)
    uvicorn.run(app, host=host, port=port)
