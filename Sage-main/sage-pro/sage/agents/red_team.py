import asyncio
import structlog
import ast
import hashlib
from typing import Dict, List, Any
from sage.agents.base import VLLMAgent

logger = structlog.get_logger(__name__)

class RedTeam:
    """The Red-Team specialist ensemble.

    Uses a dual-model ensemble (DeepSeek-Coder + StarCoder2) to find vulnerabilities, 
    generate adversarial tests, and perform asymptotic analysis.
    """

    def __init__(
        self, 
        base_url: str,
        primary_model: str,
        secondary_model: str,
        primary_temperature: float,
        secondary_temperature: float,
        prompt_path: str,
        udrk_prompt: str = "",
    ) -> None:
        """Initializes the Red-Team ensemble."""
        self.primary = VLLMAgent(
            name="RedTeam-Primary",
            base_url=base_url,
            model_name=primary_model,
            temperature=primary_temperature,
            system_prompt_path=prompt_path,
            udrk_prompt=udrk_prompt,
        )
        self.secondary = VLLMAgent(
            name="RedTeam-Secondary",
            base_url=base_url,
            model_name=secondary_model,
            temperature=secondary_temperature,
            system_prompt_path=prompt_path,
            udrk_prompt=udrk_prompt,
        )

    async def attack(self, code: str, spec: str) -> Dict[str, Any]:
        """Performs an adversarial attack on a code proposal.

        Args:
            code: The Python code to attack.
            spec: The original architectural specification.

        Returns:
            A dictionary containing tests, strategies, findings, and analysis.
        """
        user_msg = (
            f"Code Proposal:\n{code}\n\n"
            f"Spec:\n{spec}\n\n"
            f"Find flaws, generate adversarial pytest cases, and provide Big-O analysis."
        )

        # Fan-out to both models
        responses = await asyncio.gather(
            self.primary.complete(user_msg),
            self.secondary.complete(user_msg),
            return_exceptions=True
        )

        findings: List[str] = []
        tests: List[str] = []
        
        for resp in responses:
            if isinstance(resp, BaseException):
                logger.error("red_team_sub_agent_failed", error=str(resp))
                continue
            
            # Basic parsing of the raw response (assuming Markdown blocks)
            # In a real system, we'd use a more robust parser or JSON mode.
            findings.append(resp.content)
            
            # Extract code blocks as tests
            # Simplified: assuming the LLM puts tests in ```python blocks
            if resp.code:
                tests.append(resp.code)

        # Deduplicate tests by AST hash
        unique_tests = []
        seen_hashes = set()
        for t in tests:
            try:
                tree = ast.parse(t)
                t_hash = hashlib.md5(ast.dump(tree).encode()).hexdigest()
                if t_hash not in seen_hashes:
                    unique_tests.append(t)
                    seen_hashes.add(t_hash)
            except:
                continue

        return {
            "tests": "\n\n".join(unique_tests),
            "hypothesis_strategy": "st.text()", # Placeholder for strategy extraction
            "security_findings": findings,
            "big_o_analysis": "O(N log N)" # Placeholder for extraction
        }
