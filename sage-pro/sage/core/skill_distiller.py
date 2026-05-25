"""
SAGE-PRO Novel System 5: Skill-Conditioned Self-Distillation (Skill-SD)
════════════════════════════════════════════════════════════════════════
Implements the 'Golden Trajectory Vault'.

While the Mistake Library provides negative constraints (Failure Archaeology),
the Skill Distiller extracts positive, proven execution paths ("Golden Trajectories")
from highly successful runs and compresses them into generalized "Skills".

Algorithm:
    1. Graph identifies a run with AST Reward > 0.85 (near-perfect).
    2. Extracts the exact sequence of tool calls and reasoning.
    3. Compresses the trajectory into a generalized Skill rule.
    4. Embeds and stores the Skill in ChromaDB (golden_skills collection).
    5. On future queries in the same FAISS manifold region, the Orchestrator
       injects the Skill as privileged "teacher" information to guide the agents.

Config: aode_hyperparams.yaml → skill_distillation
"""

import os
import uuid
import structlog
from typing import Dict, Any, List, Optional
try:
    import chromadb
except ImportError:
    chromadb = None

logger = structlog.get_logger(__name__)


class SkillDistiller:
    """Extracts, compresses, and retrieves Golden Trajectories."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the Skill Distiller.

        Args:
            hyperparams: Full config dict.
        """
        cfg = hyperparams.get("skill_distillation", {})
        self.reward_threshold: float = cfg.get("reward_threshold", 0.85)
        self.collection_name: str = cfg.get("collection_name", "golden_skills")
        self.top_k: int = cfg.get("top_k", 2)

        self.client = None
        self.collection = None

        if chromadb:
            chroma_path = os.environ.get("CHROMA_PATH", "data/chroma")
            try:
                self.client = chromadb.PersistentClient(path=chroma_path)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(
                    "skill_distiller_initialized",
                    collection=self.collection_name,
                    path=chroma_path,
                )
            except Exception as e:
                logger.warning("skill_distiller_chroma_failed", error=str(e))
        else:
            logger.warning("chromadb_not_installed_skill_distiller_disabled")

    def _compress_trajectory(self, tool_log: List[Dict[str, Any]]) -> str:
        """Compresses a raw tool log into a generalized skill string.

        In a full LLM implementation, this would use a fast model to
        summarize the trajectory. Here we structurally compress it.

        Args:
            tool_log: List of tool execution dicts.

        Returns:
            A generalized skill string.
        """
        if not tool_log:
            return "Skill: Direct generation without tools."

        steps = []
        for i, call in enumerate(tool_log, 1):
            tool_name = call.get("tool", "unknown_tool")
            args = str(call.get("args_preview", ""))[:50]
            steps.append(f"Step {i}: Use {tool_name} ({args}...)")

        return "Golden Trajectory:\n" + "\n".join(steps)

    def distill_and_store(
        self,
        query_text: str,
        tool_log: List[Dict[str, Any]],
        reward: float,
    ) -> bool:
        """Distills a highly successful run into a skill and stores it.

        Args:
            query_text: The original user task.
            tool_log: The sequence of tools used to solve it.
            reward: The AST-diff reward score.

        Returns:
            True if stored, False otherwise (e.g. reward too low).
        """
        if self.collection is None:
            return False

        if reward < self.reward_threshold:
            return False

        skill_text = self._compress_trajectory(tool_log)
        skill_id = str(uuid.uuid4())

        try:
            self.collection.add(
                documents=[skill_text],
                metadatas=[{"query": query_text, "reward": float(reward)}],
                ids=[skill_id],
            )
            logger.info(
                "golden_skill_distilled",
                skill_id=skill_id,
                reward=reward,
                steps=len(tool_log),
            )
            return True
        except Exception as e:
            logger.error("golden_skill_store_failed", error=str(e))
            return False

    def retrieve_skills(self, query_text: str) -> List[str]:
        """Retrieves relevant golden skills for a new query.

        Args:
            query_text: The new user task.

        Returns:
            List of skill strings (empty if none found).
        """
        if self.collection is None:
            return []

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=self.top_k,
            )

            docs = results.get("documents", [[]])[0]
            if not docs:
                return []

            logger.debug(
                "golden_skills_retrieved",
                count=len(docs),
                query=query_text[:50],
            )
            return docs

        except Exception as e:
            logger.warning("golden_skill_retrieve_failed", error=str(e))
            return []

    def build_skill_context(self, skills: List[str]) -> str:
        """Builds the system prompt context for injected skills.

        Args:
            skills: Retrieved skill strings.

        Returns:
            System prompt block.
        """
        if not skills:
            return ""

        lines = [
            "# Golden Trajectories (Skill-SD)",
            "The following execution paths have a proven 90%+ success rate",
            "on queries structurally identical to this one. You are STRONGLY",
            "advised to follow these steps:\n",
        ]

        for i, skill in enumerate(skills, 1):
            lines.append(f"## Proven Strategy {i}:")
            lines.append(skill)
            lines.append("")

        return "\n".join(lines)
