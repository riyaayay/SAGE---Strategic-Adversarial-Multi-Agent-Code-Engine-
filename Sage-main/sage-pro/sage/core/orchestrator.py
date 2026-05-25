"""
SAGE-PRO Orchestrator Node
════════════════════════════
The master reasoning coordinator that drives the tool-calling loop.

Implements the full pre-flight sequence from the Tool Orchestrator spec:
  1. memory_query (always first)
  2. Build grocery list
  3. Execute grocery run (tool calls)
  4. Dispatch to agents with full context
  5. Synthesize and verify
  6. Store learnings

Wired into the LangGraph pipeline via build_graph().

Config:
    Tool definitions from configs/tool_definitions.json
    Orchestrator prompt from sage/prompts/orchestrator.md
    Agent charters from sage/prompts/{agent}_charter.md
    Ollama settings from configs/aode_hyperparams.yaml → ollama
"""

import os
import json
import httpx
import structlog
from typing import Dict, Any, List, Optional
from pathlib import Path

from sage.tools.tool_dispatcher import load_tool_definitions, handle_tool_calls

logger = structlog.get_logger(__name__)

# ─── Soft-coded Ollama settings ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

# Max tool-call rounds before forcing a final answer
MAX_TOOL_ROUNDS = int(os.environ.get("ORCHESTRATOR_MAX_TOOL_ROUNDS", "6"))


def _load_prompt(path: str) -> str:
    """Loads a prompt file from disk.

    Args:
        path: Relative path to the prompt file.

    Returns:
        The prompt text, or empty string if not found.
    """
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    logger.warning("prompt_not_found", path=path)
    return ""


def load_agent_charters() -> Dict[str, str]:
    """Loads all agent tool charters from their prompt files.

    Returns:
        Dict mapping agent_name → charter text.
    """
    return {
        "orchestrator": _load_prompt("sage/prompts/orchestrator.md"),
        "architect": _load_prompt("sage/prompts/architect_charter.md"),
        "implementer": _load_prompt("sage/prompts/implementer_charter.md"),
        "synthesizer": _load_prompt("sage/prompts/synthesizer_charter.md"),
        "red_team": _load_prompt("sage/prompts/red_team_charter.md"),
    }


async def ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict]] = None,
    temperature: float = 0.1,
    num_ctx: int = 32768,
) -> Dict[str, Any]:
    """Makes a single Ollama /api/chat call.

    Args:
        model: Ollama model name (e.g. "qwen2.5-coder:72b").
        messages: Conversation messages.
        tools: Tool definitions (optional).
        temperature: Sampling temperature.
        num_ctx: Context window size.

    Returns:
        The Ollama response dict.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_gpu": -1,
        },
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def run_orchestrator_loop(
    user_message: str,
    model: str,
    hyperparams: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    project_root: str = ".",
) -> Dict[str, Any]:
    """Runs the full orchestrator tool-calling loop.

    This is the main entry point for the SAGE-PRO orchestrator.
    It implements the mandatory pre-flight sequence:
      1. Load system prompt + tool charters
      2. Send to Ollama with tools enabled
      3. If tool_calls returned → dispatch → feed results back → repeat
      4. When no more tool_calls → return final response

    Args:
        user_message: The user's query.
        model: Ollama model to use for the orchestrator.
        hyperparams: Full hyperparams dict.
        conversation_history: Prior messages (if continuing a conversation).
        project_root: Root directory for file operations.

    Returns:
        Dict with 'response' (the final text) and 'tool_log' (all tool calls).
    """
    charters = load_agent_charters()
    tools = load_tool_definitions()

    # Build messages
    messages = [
        {"role": "system", "content": charters.get("orchestrator", "")},
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    tool_log: List[Dict[str, Any]] = []

    for round_idx in range(MAX_TOOL_ROUNDS):
        logger.info("orchestrator_round", round=round_idx + 1)

        response = await ollama_chat(
            model=model,
            messages=messages,
            tools=tools,
            temperature=hyperparams.get("orchestrator_temperature", 0.1),
            num_ctx=hyperparams.get("orchestrator_num_ctx", 32768),
        )

        message = response.get("message", {})

        # Check if the model wants to call tools
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No more tool calls — we have a final answer
            final_text = message.get("content", "")
            logger.info(
                "orchestrator_complete",
                rounds=round_idx + 1,
                tool_calls_total=len(tool_log),
            )
            return {
                "response": final_text,
                "tool_log": tool_log,
                "rounds": round_idx + 1,
            }

        # Dispatch tool calls
        messages.append(message)  # Add assistant's tool-call message

        tool_results = await handle_tool_calls(response, project_root)

        for tr in tool_results:
            tool_log.append({
                "tool": tr["name"],
                "result_preview": tr["content"][:200],
            })

        # Add tool results to conversation
        messages.extend(tool_results)

    # If we exhausted all rounds, return whatever we have
    logger.warning("orchestrator_max_rounds_reached", max=MAX_TOOL_ROUNDS)
    final_response = await ollama_chat(
        model=model,
        messages=messages + [
            {"role": "user", "content": "You have reached the maximum tool rounds. Please provide your final answer now."}
        ],
        tools=None,  # No more tools — force text response
    )

    return {
        "response": final_response.get("message", {}).get("content", ""),
        "tool_log": tool_log,
        "rounds": MAX_TOOL_ROUNDS,
        "truncated": True,
    }


async def run_agent_with_tools(
    agent_name: str,
    model: str,
    task_context: str,
    hyperparams: Dict[str, Any],
    allowed_tools: Optional[List[str]] = None,
    project_root: str = ".",
) -> Dict[str, Any]:
    """Runs a single agent with its tool charter and authorized tools.

    Args:
        agent_name: "architect", "implementer", "synthesizer", or "red_team".
        model: Ollama model to use for this agent.
        task_context: The full context to give the agent.
        hyperparams: Full hyperparams dict.
        allowed_tools: List of tool names this agent may use. None = all.
        project_root: Root directory for file operations.

    Returns:
        Dict with 'response' and 'tool_log'.
    """
    charters = load_agent_charters()
    all_tools = load_tool_definitions()

    # Filter tools to only those allowed for this agent
    if allowed_tools:
        tools = [t for t in all_tools if t["function"]["name"] in allowed_tools]
    else:
        tools = all_tools

    # Build agent-specific system prompt: UDRK + charter
    charter = charters.get(agent_name, "")

    messages = [
        {"role": "system", "content": charter},
        {"role": "user", "content": task_context},
    ]

    tool_log: List[Dict[str, Any]] = []

    for round_idx in range(MAX_TOOL_ROUNDS):
        response = await ollama_chat(
            model=model,
            messages=messages,
            tools=tools if tools else None,
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            return {
                "response": message.get("content", ""),
                "tool_log": tool_log,
                "rounds": round_idx + 1,
            }

        messages.append(message)
        tool_results = await handle_tool_calls(response, project_root)
        for tr in tool_results:
            tool_log.append({"tool": tr["name"], "result_preview": tr["content"][:200]})
        messages.extend(tool_results)

    return {
        "response": "Agent reached max tool rounds without final answer.",
        "tool_log": tool_log,
        "rounds": MAX_TOOL_ROUNDS,
        "truncated": True,
    }
