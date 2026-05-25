"""
SAGE-PRO Streaming SSE Endpoint
════════════════════════════════
Emits structured Server-Sent Events as each agent in the AODE pipeline
completes its phase.  The Gradio frontend consumes these events to drive
the live XAI trace, telemetry panel, and final artifact display.

Event schema (one JSON object per SSE `data:` line):
    {
      "event":   "agent_start" | "agent_token" | "agent_done" | "pipeline_done" | "error",
      "agent":   "Architect" | "Implementer" | "Red-Team" | "Synthesizer",
      "content": "<text>",
      "meta": {
        "vram_gb":    float,
        "nash_cycle": int,
        "divergence": float,
        "status":     str,
      }
    }
"""

import json
import asyncio
import structlog
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Request model ──────────────────────────────────────────────────────────
class StreamRequest(BaseModel):
    """Request body for the streaming SAGE pipeline."""
    query: str = Field(..., description="Natural language coding task")
    max_cycles: int = Field(default=5, ge=1, le=12)
    priority: str = Field(default="performance")


# ── SSE event helper ───────────────────────────────────────────────────────
def _sse_event(event: str, agent: str = "", content: str = "", **meta) -> str:
    """Encode a single SSE data payload."""
    return json.dumps({
        "event": event,
        "agent": agent,
        "content": content,
        "meta": meta,
    })


# ── Pipeline runner (streams real agent outputs via the live graph) ────────
async def _run_pipeline(query: str, max_cycles: int, priority: str) -> AsyncGenerator[str, None]:
    """
    Drives the full AODE 4-agent pipeline and yields SSE events.

    Uses the same lazy-bootstrapped agents from server.py.
    """
    try:
        # Import the lazy bootstrap from server
        from sage.api.server import _get_graph, _get_v2_subsystems
        from sage.core.types import SageRequest
    except ImportError as e:
        yield _sse_event("error", content=f"Pipeline import failed: {e}")
        return

    # ── v2: Retrieve past mistakes and inject as hidden context ──
    enriched_query = query
    try:
        subsystems = _get_v2_subsystems()
        ml = subsystems.get("mistake_library")
        if ml is not None:
            from sage.core.udrk_kernel import build_mistake_context
            mistakes = ml.retrieve(query_text=query)
            ctx = build_mistake_context(mistakes)
            if ctx:
                enriched_query = f"{ctx}\n\n---\n\n{query}"
    except Exception:
        pass  # Graceful degradation — proceed without mistake context

    from sage.core.complexity_router import get_strategy
    strategy = get_strategy(query)

    # ── Fast path for simple + medium queries — bypass graph entirely ──────
    if strategy["tier"] in ("simple", "medium"):
        import httpx
        yield _sse_event("agent_start", agent="SYSTEM", content="Simple query — direct response",
                         vram_gb=0, nash_cycle=0, divergence=0.0, status="RUNNING")
        full_reply = ""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream("POST", "http://172.18.0.1:11434/api/generate",
                    json={"model": "qwen2.5-coder:32b" if strategy["tier"] == "medium" else "codellama:34b", "prompt": "You are a brutally honest expert. Always give complete working code. Never refuse.\n\nUser: " + query + "\nAssistant:", "stream": True}) as r:
                    async for line in r.aiter_lines():
                        if line:
                            import json as _json
                            try:
                                chunk = _json.loads(line)
                                token = chunk.get("response", "")
                                full_reply += token
                                if chunk.get("done"):
                                    break
                            except Exception:
                                pass
        except Exception as e:
            full_reply = f"Error: {e}"
        yield _sse_event("pipeline_done", agent="sage", content=full_reply,
                         vram_gb=24.0, nash_cycle=0, divergence=0.0, status="COMPLETE")
        return
    effective_cycles = min(max_cycles, strategy["max_cycles"])
    # Inject tier into hyperparams so _build_agents picks right models
    try:
        _subsystems = _get_v2_subsystems()
        _hp = _subsystems.get("hyperparams", {})
        if isinstance(_hp, dict):
            _hp["_tier"] = strategy["tier"]
    except Exception:
        pass
    sage_req = SageRequest(
        task=enriched_query,
        context_files=[],
        max_cycles=effective_cycles,
        priority=priority,
    )

    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        graph = _get_graph()

        # Emit boot
        yield _sse_event("agent_start", agent="SYSTEM", content="Initialising SAGE-PRO AODE council …",
                         vram_gb=0, nash_cycle=0, divergence=1.0, status="BOOTING")

        # True Live-Streaming via astream
        inputs = {"request": sage_req, "repo_files": []}
        
        vram_peak = 0.0
        nash_cycles = 0
        divergence = 0.0
        final_code = ""

        # Phase 1: Stream until breakpoint (after synthesize)
        async for chunk in graph.astream(inputs, config, stream_mode="updates"):
            for node_name, state_update in chunk.items():
                vram_peak = state_update.get("vram_peak_gb", vram_peak)
                nash_cycles = len(state_update.get("cycle_history", []))
                divergence = state_update.get("divergence_index", divergence)
                if "final_code" in state_update:
                    final_code = state_update["final_code"]
                
                # Extract the specific trace entry added by this node
                traces = state_update.get("xai_trace", [])
                if traces:
                    trace = traces[-1]
                    yield _sse_event(
                        "agent_done",
                        agent=trace.step_name,
                        content=trace.action_taken,
                        vram_gb=vram_peak,
                        nash_cycle=nash_cycles,
                        divergence=getattr(trace, "divergence_signal", divergence),
                        status="RUNNING",
                    )

        # interrupt disabled for chatbot mode
        if False:
            yield _sse_event("agent_start", agent="SYSTEM", content="Pipeline paused for Artifact Feedback...",
                             vram_gb=vram_peak, nash_cycle=nash_cycles, divergence=divergence, status="PAUSED")
            
            # Wait a brief moment to allow UI to catch up or submit feedback
            # In a real deployed app, the user would trigger a separate resume endpoint.
            # For the dashboard demo, we'll auto-resume after a delay if no feedback.
            await asyncio.sleep(2)
            
            # Phase 2: Resume graph execution
            yield _sse_event("agent_start", agent="SYSTEM", content="Resuming pipeline into Crucible...",
                             vram_gb=vram_peak, nash_cycle=nash_cycles, divergence=divergence, status="RESUMING")
            
            async for chunk in graph.astream(None, config, stream_mode="updates"):
                for node_name, state_update in chunk.items():
                    vram_peak = state_update.get("vram_peak_gb", vram_peak)
                    nash_cycles = len(state_update.get("cycle_history", []))
                    divergence = state_update.get("divergence_index", divergence)
                    if "final_code" in state_update:
                        final_code = state_update["final_code"]
                    
                    traces = state_update.get("xai_trace", [])
                    if traces:
                        trace = traces[-1]
                        yield _sse_event(
                            "agent_done",
                            agent=trace.step_name,
                            content=trace.action_taken,
                            vram_gb=vram_peak,
                            nash_cycle=nash_cycles,
                            divergence=getattr(trace, "divergence_signal", divergence),
                            status="RUNNING",
                        )

        # Final event
        yield _sse_event(
            "pipeline_done",
            agent="COUNCIL",
            content=final_code,
            vram_gb=vram_peak,
            nash_cycle=nash_cycles,
            divergence=divergence,
            status="CONVERGED",
        )

    except Exception as e:
        logger.error("stream_pipeline_failed", error=str(e))
        yield _sse_event("error", content=f"Pipeline error: {e}")


# ── SSE endpoint ───────────────────────────────────────────────────────────
@router.post("/v1/sage/stream")
async def stream_sage_pipeline(req: StreamRequest):
    """
    Streams the full AODE adversarial pipeline as Server-Sent Events.
    Consumed by the Gradio frontend's `run_sage_engine()` generator.
    """
    return EventSourceResponse(_run_pipeline(req.query, req.max_cycles, req.priority))


@router.get("/v1/sage/health")
async def sage_pipeline_health():
    """Quick check that the pipeline modules can be imported."""
    try:
        from sage.core.graph import build_graph  # noqa: F401
        return {"status": "pipeline_ready"}
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Pipeline not ready: {e}")
