import structlog
from sage.agents.base import VLLMAgent

logger = structlog.get_logger(__name__)

class Implementer(VLLMAgent):
    """The Implementer specialist agent.

    Responsible for turning design specifications into working code. 
    Optimized for code generation using DeepSeek-Coder-V2.
    """

    def __init__(
        self, 
        base_url: str, 
        model_name: str,
        prompt_path: str,
        temperature: float,
        udrk_prompt: str = "",
    ) -> None:
        """Initializes the Implementer with specialized parameters for MI300X."""
        super().__init__(
            name="Implementer",
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            system_prompt_path=prompt_path,
            udrk_prompt=udrk_prompt,
        )

    async def implement(self, spec: str, torsion_suffix: str) -> str:
        """Generates Python code based on an architectural specification.

        Args:
            spec: The design specification from the Architect.
            torsion_suffix: An architectural nudge (torsion) to explore alternative manifolds.

        Returns:
            The generated Python source code.
        """
        user_msg = (
            f"Design Spec:\n{spec}\n\n"
            f"Constraints/Nudges:\n{torsion_suffix}\n\n"
            f"Implement the solution in Python. Ensure full type hints and docstrings."
        )
        
        response = await self.complete(user_msg)
        return response.content
