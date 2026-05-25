"""
SAGE-PRO Novel System 6: Topological Self-Play (Chaos Auto-Curriculum)
════════════════════════════════════════════════════════════════════════
Implements an "AlphaZero for Code" paradigm.

Instead of waiting for user queries to update the CTR Q-table, this
system runs during downtime. It actively selects highly-trusted regions
of the FAISS manifold, introduces subtle structural bugs (chaos) into
the actual repository, and forces the agents to detect and heal them.

If the agents succeed, the Q-table is reinforced. If they fail, the
failure is embedded into the Execution Trace Mistake Library, and the
file is reverted.

Algorithm:
    1. Select a high-confidence FAISS centroid (W > 0.8).
    2. Retrieve files mathematically nearest to that centroid.
    3. Chaos Agent injects a semantic bug (e.g. edge-case logic flaw).
    4. Orchestrator is dispatched to "audit and fix" the file.
    5. Reward is calculated via AST Diff Reward Crystallizer.
    6. Q-table updated. File is reverted to original state.

Config: aode_hyperparams.yaml → chaos_curriculum
"""

import os
import random
import difflib
import asyncio
import structlog
from typing import Dict, Any, List, Tuple

logger = structlog.get_logger(__name__)


class ChaosCurriculumEngine:
    """Manages autonomous self-play by injecting and repairing bugs."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the chaos engine.

        Args:
            hyperparams: Full config dict.
        """
        cfg = hyperparams.get("chaos_curriculum", {})
        self.enabled: bool = cfg.get("enabled", False)
        self.max_daily_games: int = cfg.get("max_daily_games", 5)
        self.target_q_threshold: float = cfg.get("target_q_threshold", 0.6)

        self._games_played_today: int = 0
        logger.info("chaos_curriculum_init", enabled=self.enabled)

    def select_target_cluster(
        self, q_table: Dict[Tuple[int, int], float]
    ) -> int:
        """Finds a highly-trusted cluster in the Q-table.

        We want to attack our STRONGEST domains to ensure the
        agents aren't overfitting or relying on brittle logic.

        Args:
            q_table: The CTR Engine Q-table.

        Returns:
            Cluster ID to attack, or -1 if none suitable.
        """
        # Group max Q by cluster
        cluster_max = {}
        for (cid, _), q_val in q_table.items():
            if cid not in cluster_max or q_val > cluster_max[cid]:
                cluster_max[cid] = q_val

        strong_clusters = [
            cid for cid, max_q in cluster_max.items()
            if max_q > self.target_q_threshold
        ]

        if not strong_clusters:
            return -1

        return random.choice(strong_clusters)

    async def generate_chaos_mutation(
        self,
        file_content: str,
        ollama_chat_fn: Any,
        model: str = "qwen2.5:72b"
    ) -> str:
        """Uses a Red Team prompt to inject a subtle, realistic bug.

        Args:
            file_content: Original source code.
            ollama_chat_fn: Function to call Ollama.
            model: Model to use for bug generation.

        Returns:
            Mutated source code.
        """
        prompt = """You are a Chaos Engineering Agent.
Your task is to take the following Python code and introduce ONE subtle,
realistic bug. Do NOT introduce syntax errors. The code must still run,
but it should fail on an edge case.

Examples:
- Change a `<` to `<=` causing an off-by-one.
- Remove a `not` operator in an obscure condition.
- Mutate a dictionary key name slightly.
- Return early before a critical cleanup step.

Return ONLY the fully complete, modified Python code. No markdown formatting
except the ```python block.
"""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": file_content}
        ]

        try:
            response = await ollama_chat_fn(
                model=model,
                messages=messages,
                temperature=0.8,
            )
            content = response.get("message", {}).get("content", "")

            # Extract code block
            if "```python" in content:
                content = content.split("```python")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return content.strip()
        except Exception as e:
            logger.error("chaos_mutation_failed", error=str(e))
            return file_content

    async def run_self_play_game(
        self,
        target_file: str,
        ollama_chat_fn: Any,
        orchestrator_fn: Any,
        project_root: str = "."
    ) -> Dict[str, Any]:
        """Executes one round of Topological Self-Play.

        Args:
            target_file: Path to the file to attack.
            ollama_chat_fn: Ollama chat function (for bug injection).
            orchestrator_fn: The main /v1/orchestrate function.
            project_root: Root of the repository.

        Returns:
            Result dictionary containing success metric.
        """
        if not self.enabled or self._games_played_today >= self.max_daily_games:
            return {"status": "skipped"}

        full_path = os.path.join(project_root, target_file)
        if not os.path.exists(full_path):
            return {"status": "file_not_found"}

        with open(full_path, "r", encoding="utf-8") as f:
            original_code = f.read()

        # 1. Inject Chaos
        logger.info("chaos_game_started", target=target_file)
        mutated_code = await self.generate_chaos_mutation(
            original_code, ollama_chat_fn
        )

        if mutated_code == original_code:
            return {"status": "mutation_failed"}

        # Write mutated code to disk temporarily
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(mutated_code)

        try:
            # 2. Dispatch Orchestrator to fix it
            task = (
                f"Audit `{target_file}`. A subtle edge-case bug has "
                f"been detected in this file. Find it and fix it. "
                f"Use your tools to read the file, write the correction, "
                f"and verify it."
            )

            result = await orchestrator_fn(
                user_message=task,
                project_root=project_root
            )

            # 3. Read the final state of the file
            with open(full_path, "r", encoding="utf-8") as f:
                final_code = f.read()

            # 4. Evaluate success: Did it restore the original intent?
            # We measure Levenshtein similarity to the ORIGINAL, unmutated code.
            matcher = difflib.SequenceMatcher(None, original_code, final_code)
            similarity = matcher.ratio()

            success = similarity > 0.95

            self._games_played_today += 1
            logger.info(
                "chaos_game_complete",
                target=target_file,
                success=success,
                similarity=similarity,
                rounds=result.get("rounds", 0)
            )

            return {
                "status": "completed",
                "success": success,
                "similarity": similarity,
                "original_mutated": mutated_code != original_code
            }

        finally:
            # 5. ALWAYS revert the file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(original_code)

    def reset_daily_counter(self) -> None:
        """Resets the daily game counter."""
        self._games_played_today = 0
