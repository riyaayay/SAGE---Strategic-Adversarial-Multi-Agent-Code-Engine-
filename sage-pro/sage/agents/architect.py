import structlog
from typing import List, Optional
from sage.agents.base import VLLMAgent

logger = structlog.get_logger(__name__)

class Architect(VLLMAgent):
    """The Architect specialist agent.

    Responsible for high-level design, structure, and identifying novel 
    topological voids in the codebase. Uses Qwen2.5-Coder-32B.
    """

    def __init__(
        self, 
        base_url: str, 
        model_name: str,
        prompt_path: str,
        temperature: float,
        udrk_prompt: str = "",
    ) -> None:
        """Initializes the Architect with specialized parameters for MI300X."""
        super().__init__(
            name="Architect",
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            system_prompt_path=prompt_path,
            udrk_prompt=udrk_prompt,
        )

    async def design(self, task: str, context_files: List[str]) -> str:
        """Generates a high-level architectural design for a task.

        Args:
            task: The natural language coding task.
            context_files: List of paths or contents of relevant files.

        Returns:
            The design specification string.
        """
        context_str = "\n".join(context_files)
        user_msg = (
            f"Task: {task}\n\n"
            f"Current Context:\n{context_str}\n\n"
            f"Produce a detailed design specification. Focus on topological robustness."
        )
        
        response = await self.complete(user_msg)
        return response.content
