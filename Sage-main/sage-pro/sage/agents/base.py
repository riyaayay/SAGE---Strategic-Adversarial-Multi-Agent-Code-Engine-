"""
SAGE-PRO VLLMAgent Base Class
═════════════════════════════
Base class for all SAGE agents. Communicates with vLLM/Ollama endpoints
via the OpenAI-compatible HTTP API.

Supports:
- Non-streaming chat completions with retry + exponential backoff
- SSE token streaming for real-time UI updates
- Optional logit_bias injection for torsion enforcement at the token level
"""

import asyncio
import json
import httpx
import structlog
import time
import hashlib
from typing import AsyncGenerator, Optional, List, Dict
from pathlib import Path

from sage.core.types import AgentResponse, XAITrace

logger = structlog.get_logger(__name__)


class VLLMAgent:
    """Base class for SAGE agents interacting with vLLM endpoints via OpenAI-compatible HTTP.

    This class handles prompt loading, request retries with exponential backoff,
    logit_bias injection for torsion enforcement, and XAI trace logging.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        model_name: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        system_prompt_path: Optional[str] = None,
        udrk_prompt: str = "",
        api_timeout_sec: float = 300.0,
        api_max_retries: int = 3,
    ) -> None:
        """Initializes the VLLMAgent.

        Args:
            name: Human-readable name of the agent.
            base_url: The vLLM server URL (e.g. http://localhost:8001/v1).
            model_name: The identifier of the model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            system_prompt_path: Path to the markdown file containing the system prompt.
        """
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_timeout_sec = api_timeout_sec
        self.api_max_retries = api_max_retries
        self.system_prompt = udrk_prompt
        
        if system_prompt_path:
            path = Path(system_prompt_path)
            if path.exists():
                file_prompt = path.read_text(encoding="utf-8")
                self.system_prompt = f"{self.system_prompt}\n\n{file_prompt}".strip()
                logger.info("agent_prompt_loaded", agent=name, path=system_prompt_path)
            else:
                logger.warning("agent_prompt_not_found", agent=name, path=system_prompt_path)

    async def complete(
        self,
        user_msg: str,
        extra_system: str = "",
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> AgentResponse:
        """Performs a non-streaming chat completion.

        Args:
            user_msg: The user's input message.
            extra_system: Optional additional system instructions.
            logit_bias: Optional dict mapping token IDs to bias values.
                When provided, these biases are applied at the logit level
                during generation, enforcing torsion constraints mathematically
                rather than via prompt engineering.

        Returns:
            An AgentResponse containing the generated content and metadata.
        """
        full_system = f"{self.system_prompt}\n\n{extra_system}".strip()
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_msg},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        # Inject logit_bias for torsion enforcement at the token level
        if logit_bias:
            payload["logit_bias"] = {str(k): v for k, v in logit_bias.items()}

        async with httpx.AsyncClient(timeout=self.api_timeout_sec) as client:
            retries = 0
            while retries <= self.api_max_retries:
                try:
                    start_time = time.time()
                    response = await client.post(
                        f"{self.base_url}/chat/completions", json=payload,
                    )

                    if response.status_code >= 500 and retries < self.api_max_retries:
                        retries += 1
                        wait_time = 2 ** retries
                        logger.warning(
                            "vllm_retry",
                            agent=self.name,
                            status=response.status_code,
                            wait=wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    latency_ms = (time.time() - start_time) * 1000

                    # Record XAI Trace
                    prompt_hash = hashlib.md5(user_msg.encode()).hexdigest()[:8]
                    trace = XAITrace(
                        step_name=f"{self.name}_completion",
                        operator="inference",
                        divergence_signal=0.0,
                        action_taken=f"Generated {len(content)} chars (Prompt hash: {prompt_hash})",
                    )

                    # Extract code blocks from the response
                    extracted_code = self._extract_code_block(content)

                    return AgentResponse(
                        agent_name=self.name,
                        content=content,
                        code=extracted_code,
                        latency_ms=latency_ms,
                        thought_trace=[f"Prompt hash: {prompt_hash}"],
                    )

                except Exception as e:
                    if retries >= self.api_max_retries:
                        logger.error("vllm_completion_failed", agent=self.name, error=str(e))
                        raise
                    retries += 1
                    await asyncio.sleep(2 ** retries)
            
            raise RuntimeError(f"vLLM completion failed for {self.name} after {self.api_max_retries} retries")

    @staticmethod
    def _extract_code_block(text: str) -> str | None:
        """Extracts the first ```python code block from an LLM response.

        Args:
            text: Raw LLM response text.

        Returns:
            The extracted code string, or None if no block found.
        """
        import re
        pattern = r"```(?:python)?\s*\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    async def stream(
        self,
        user_msg: str,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> AsyncGenerator[str, None]:
        """Yields tokens via Server-Sent Events (SSE) for real-time UI updates.

        Args:
            user_msg: The user's input message.
            logit_bias: Optional dict mapping token IDs to bias values
                for torsion enforcement at the logit level.

        Yields:
            The incremental tokens as strings.
        """
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }

        # Inject logit_bias for torsion enforcement at the token level
        if logit_bias:
            payload["logit_bias"] = {str(k): v for k, v in logit_bias.items()}

        async with httpx.AsyncClient(timeout=self.api_timeout_sec) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            token = data["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
