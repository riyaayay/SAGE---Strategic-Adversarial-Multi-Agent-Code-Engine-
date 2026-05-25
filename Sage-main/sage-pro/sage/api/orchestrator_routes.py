"""
SAGE-PRO Orchestrator API Endpoint
════════════════════════════════════
Provides the /v1/orchestrate endpoint that runs the full
tool-calling orchestrator loop with all 8 tools.

This is the production endpoint that replaces the basic /v1/code
for tool-augmented generation.
"""

import json
import asyncio
import structlog
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["orchestrator"])


class OrchestrateRequest(BaseModel):
    """Request body for the orchestrator endpoint."""
    query: str = Field(..., description="Natural language query or task")
    model: str = Field(default="", description="Override the orchestrator model")
    max_tool_rounds: int = Field(default=0, description="Override max tool rounds (0 = use config)")
    project_root: str = Field(default=".", description="Project root for file ops")


class OrchestrateResponse(BaseModel):
    """Response from the orchestrator."""
    response: str
    tool_log: list
    rounds: int
    truncated: bool = False


@router.post("/v1/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest):
    """Runs the full SAGE-PRO orchestrator with tool-calling loop.

    This is the main production endpoint. It:
      1. Loads tool definitions from config
      2. Runs the orchestrator system prompt
      3. Dispatches tool calls to implementations
      4. Loops until the model produces a final answer
      5. Returns the response with tool provenance log
    """
    from sage.api.server import _load_hyperparams
    from sage.core.orchestrator import run_orchestrator_loop

    hyperparams = _load_hyperparams()
    ollama_cfg = hyperparams.get("ollama", {})

    model = req.model or ollama_cfg.get("models", {}).get("orchestrator", "qwen2.5:72b")

    if req.max_tool_rounds > 0:
        import os
        os.environ["ORCHESTRATOR_MAX_TOOL_ROUNDS"] = str(req.max_tool_rounds)

    try:
        result = await run_orchestrator_loop(
            user_message=req.query,
            model=model,
            hyperparams=hyperparams,
            project_root=req.project_root,
        )

        return OrchestrateResponse(
            response=result.get("response", ""),
            tool_log=result.get("tool_log", []),
            rounds=result.get("rounds", 0),
            truncated=result.get("truncated", False),
        )

    except Exception as e:
        logger.error("orchestrate_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/orchestrate/stream")
async def orchestrate_stream(req: OrchestrateRequest):
    """Streams the orchestrator output as SSE events.

    Event types:
      - tool_call: when a tool is being called
      - tool_result: when a tool returns
      - agent_dispatch: when dispatching to a sub-agent
      - final: the final response
    """
    from sage.api.server import _load_hyperparams
    from sage.core.orchestrator import ollama_chat, load_agent_charters
    from sage.tools.tool_dispatcher import load_tool_definitions, handle_tool_calls
    import os

    hyperparams = _load_hyperparams()
    ollama_cfg = hyperparams.get("ollama", {})
    model = req.model or ollama_cfg.get("models", {}).get("orchestrator", "qwen2.5:72b")
    max_rounds = req.max_tool_rounds or int(os.environ.get("ORCHESTRATOR_MAX_TOOL_ROUNDS", "6"))

    async def _stream() -> AsyncGenerator[str, None]:
        charters = load_agent_charters()
        tools = load_tool_definitions()

        messages = [
            {"role": "system", "content": charters.get("orchestrator", "")},
            {"role": "user", "content": req.query},
        ]

        for round_idx in range(max_rounds):
            yield json.dumps({
                "event": "round_start",
                "round": round_idx + 1,
            })

            response = await ollama_chat(
                model=model,
                messages=messages,
                tools=tools,
            )

            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                yield json.dumps({
                    "event": "final",
                    "content": message.get("content", ""),
                    "rounds": round_idx + 1,
                })
                return

            # Emit tool calls
            for tc in tool_calls:
                fn = tc.get("function", {})
                yield json.dumps({
                    "event": "tool_call",
                    "tool": fn.get("name", ""),
                    "args_preview": str(fn.get("arguments", {}))[:200],
                })

            messages.append(message)
            tool_results = await handle_tool_calls(response, req.project_root)

            for tr in tool_results:
                yield json.dumps({
                    "event": "tool_result",
                    "tool": tr["name"],
                    "result_preview": tr["content"][:300],
                })

            messages.extend(tool_results)

        # Force final answer
        yield json.dumps({"event": "max_rounds_reached", "max": max_rounds})

    return EventSourceResponse(_stream())
