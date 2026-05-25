"""
SAGE-PRO Tool Dispatcher
══════════════════════════
Central dispatcher that routes Ollama tool calls to their implementations.
Registered as the tool-call handler in the LangGraph orchestrator node.

All tool implementations are imported from their respective modules.
Tool definitions are loaded from configs/tool_definitions.json.
"""

import json
import os
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)

# Tool definition path — soft-coded
TOOL_DEFINITIONS_PATH = os.environ.get(
    "TOOL_DEFINITIONS_PATH",
    "configs/tool_definitions.json",
)


def load_tool_definitions() -> List[Dict[str, Any]]:
    """Loads tool definitions from the JSON config file.

    Returns:
        List of tool definition dicts for the Ollama API.
    """
    try:
        with open(TOOL_DEFINITIONS_PATH, "r", encoding="utf-8") as f:
            tools = json.load(f)
        logger.info("tool_definitions_loaded", count=len(tools))
        return tools
    except FileNotFoundError:
        logger.warning("tool_definitions_not_found", path=TOOL_DEFINITIONS_PATH)
        return []


async def dispatch_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    project_root: str = ".",
) -> Dict[str, Any]:
    """Dispatches a single tool call to its implementation.

    Args:
        tool_name: Name of the tool (from Ollama tool_call).
        arguments: The parsed arguments dict.
        project_root: Root directory for file operations.

    Returns:
        Dict with the tool's result.
    """
    try:
        if tool_name == "web_search":
            from sage.tools.web_search import tool_web_search
            return await tool_web_search(
                query=arguments["query"],
                intent=arguments["intent"],
                max_results=arguments.get("max_results", 5),
            )

        elif tool_name == "browser_fetch":
            from sage.tools.browser_fetch import tool_browser_fetch
            return await tool_browser_fetch(
                url=arguments["url"],
                extract=arguments["extract"],
                reason=arguments.get("reason", ""),
            )

        elif tool_name == "code_execute":
            from sage.tools.code_execute import tool_code_execute
            return await tool_code_execute(
                language=arguments["language"],
                code=arguments["code"],
                purpose=arguments["purpose"],
                expected_output=arguments.get("expected_output", ""),
            )

        elif tool_name == "file_read":
            from sage.tools.file_ops import tool_file_read
            return await tool_file_read(
                path=arguments["path"],
                reason=arguments["reason"],
                extract=arguments["extract"],
                project_root=project_root,
            )

        elif tool_name == "file_write":
            from sage.tools.file_ops import tool_file_write
            return await tool_file_write(
                path=arguments["path"],
                content=arguments["content"],
                mode=arguments.get("mode", "overwrite"),
                project_root=project_root,
            )

        elif tool_name == "repo_scan":
            from sage.tools.file_ops import tool_repo_scan
            return await tool_repo_scan(
                root=arguments.get("root", project_root),
                depth=arguments.get("depth", 3),
                filter_pattern=arguments.get("filter"),
            )

        elif tool_name == "memory_query":
            from sage.tools.memory_tools import tool_memory_query
            return await tool_memory_query(
                query=arguments["query"],
                top_k=arguments.get("top_k", 3),
                threshold=arguments.get("threshold", 0.82),
            )

        elif tool_name == "memory_store":
            from sage.tools.memory_tools import tool_memory_store
            return await tool_memory_store(
                original_response=arguments["original_response"],
                correction=arguments["correction"],
                domain=arguments["domain"],
                responsible_agents=arguments.get("responsible_agents", []),
            )

        else:
            logger.warning("unknown_tool_call", tool=tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error("tool_dispatch_failed", tool=tool_name, error=str(e))
        return {"error": str(e), "tool": tool_name}


async def handle_tool_calls(
    response: Dict[str, Any],
    project_root: str = ".",
) -> List[Dict[str, Any]]:
    """Extracts and executes all tool calls from an Ollama response.

    Args:
        response: The raw Ollama /api/chat response dict.
        project_root: Root directory for file operations.

    Returns:
        List of tool result messages to feed back into the conversation.
    """
    tool_results = []
    message = response.get("message", {})

    for tool_call in message.get("tool_calls", []):
        fn = tool_call.get("function", {})
        name = fn.get("name", "")
        args = fn.get("arguments", {})

        # Parse arguments if they're a string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        logger.info("tool_call_dispatching", tool=name)
        result = await dispatch_tool_call(name, args, project_root)

        tool_results.append({
            "role": "tool",
            "content": json.dumps(result, default=str),
            "name": name,
        })

    logger.info("tool_calls_complete", count=len(tool_results))
    return tool_results
