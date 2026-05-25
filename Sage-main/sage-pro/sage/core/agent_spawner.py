"""
SAGE-PRO Novel System 1: Dynamic Agent Spawner
════════════════════════════════════════════════
Detects "Topological Voids" in the FAISS manifold — clusters where
ALL current agents have consistently negative Q-values — and
autonomously spawns a new specialist agent to fill the gap.

This moves SAGE-PRO from a static multi-agent system to an
EVOLVING AGENT ECOSYSTEM.

Algorithm:
    1. For each cluster C in the Q-table:
       void_score(C) = -mean(Q(C, a) for a in agents) if all Q(C,a) < threshold
    2. If void_score(C) > spawn_threshold for N consecutive checks:
       → Extract representative queries from that cluster
       → Generate a specialist system prompt targeting that domain
       → Register the new agent in the Q-table with initial epsilon = 1.0
       → The new agent competes with existing agents via epsilon-greedy

Config (from aode_hyperparams.yaml → agent_spawner):
    void_q_threshold     — Q-value below which an agent is "failing" (default: -0.15)
    spawn_threshold      — void_score above which we spawn (default: 0.60)
    consecutive_checks   — how many checks before spawning (default: 3)
    max_spawned_agents   — cap on total spawned agents (default: 8)
    prompt_template      — template for generating specialist prompts
"""

import numpy as np
import structlog
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

logger = structlog.get_logger(__name__)


class DynamicAgentSpawner:
    """Detects topological voids and spawns specialist agents to fill them."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes the spawner from config.

        Args:
            hyperparams: Full hyperparams dict (expects 'agent_spawner' key).
        """
        cfg = hyperparams.get("agent_spawner", {})

        self.void_q_threshold: float = cfg.get("void_q_threshold", -0.15)
        self.spawn_threshold: float = cfg.get("spawn_threshold", 0.60)
        self.consecutive_checks: int = cfg.get("consecutive_checks", 3)
        self.max_spawned_agents: int = cfg.get("max_spawned_agents", 8)
        self.base_agents: List[str] = cfg.get(
            "base_agents",
            ["architect", "implementer", "synthesizer", "red_team"],
        )

        # Track consecutive void detections per cluster
        self._void_streak: Dict[int, int] = defaultdict(int)

        # Registry of spawned agents: agent_name → metadata
        self.spawned_agents: Dict[str, Dict[str, Any]] = {}

        # Representative queries per cluster (for prompt generation)
        self._cluster_queries: Dict[int, List[str]] = defaultdict(list)

        logger.info(
            "agent_spawner_initialized",
            void_threshold=self.void_q_threshold,
            spawn_threshold=self.spawn_threshold,
            max_spawned=self.max_spawned_agents,
        )

    def record_query(self, cluster_id: int, query_text: str) -> None:
        """Records a query for a cluster (for prompt generation).

        Args:
            cluster_id: The cluster this query was routed to.
            query_text: The user's query text.
        """
        buf = self._cluster_queries[cluster_id]
        buf.append(query_text)
        # Keep only last 20 queries per cluster
        if len(buf) > 20:
            self._cluster_queries[cluster_id] = buf[-20:]

    def detect_voids(
        self,
        q_table: Dict[Tuple[int, int], float],
        num_base_actions: int,
    ) -> List[Dict[str, Any]]:
        """Scans the Q-table for topological voids.

        A void is a cluster where ALL agent Q-values are below the
        void_q_threshold — meaning no current agent can handle queries
        in that region of the latent space.

        Args:
            q_table: The CTR engine's Q-table: (cluster_id, action) → Q-value.
            num_base_actions: Number of base agent actions.

        Returns:
            List of void dicts: {cluster_id, void_score, streak, queries}.
        """
        # Group Q-values by cluster
        cluster_q: Dict[int, List[float]] = defaultdict(list)
        for (cid, action), q_val in q_table.items():
            if action < num_base_actions:  # Only check base agents
                cluster_q[cid].append(q_val)

        voids = []
        for cid, q_values in cluster_q.items():
            # Check if ALL agents are failing in this cluster
            if len(q_values) < num_base_actions:
                continue

            all_below = all(q < self.void_q_threshold for q in q_values)
            if all_below:
                void_score = -np.mean(q_values)
                self._void_streak[cid] += 1
            else:
                self._void_streak[cid] = 0
                continue

            if void_score >= self.spawn_threshold:
                voids.append({
                    "cluster_id": cid,
                    "void_score": float(void_score),
                    "streak": self._void_streak[cid],
                    "mean_q": float(np.mean(q_values)),
                    "queries": self._cluster_queries.get(cid, [])[-5:],
                })

        if voids:
            logger.info("voids_detected", count=len(voids))
        return voids

    def should_spawn(self, void: Dict[str, Any]) -> bool:
        """Determines if a void warrants spawning a new agent.

        Args:
            void: A void dict from detect_voids().

        Returns:
            True if the void is severe enough and we have capacity.
        """
        if len(self.spawned_agents) >= self.max_spawned_agents:
            logger.warning("spawn_limit_reached", max=self.max_spawned_agents)
            return False

        return void["streak"] >= self.consecutive_checks

    def generate_specialist_prompt(
        self,
        void: Dict[str, Any],
        cluster_centroid: Optional[np.ndarray] = None,
    ) -> str:
        """Generates a specialist system prompt for a new agent.

        The prompt is crafted from the representative queries in the void
        cluster, telling the new agent exactly what domain it was spawned
        to handle and what the previous agents failed at.

        Args:
            void: A void dict from detect_voids().
            cluster_centroid: The FAISS centroid vector (for context).

        Returns:
            The specialist system prompt string.
        """
        queries = void.get("queries", [])
        query_block = "\n".join(f"  - {q[:120]}" for q in queries)

        prompt = f"""# Specialist Agent — Void Filler (auto-spawned)

## Why You Exist
You were dynamically spawned by the SAGE-PRO CTR engine because ALL
existing agents (Architect, Implementer, Synthesizer, Red Team)
consistently FAILED on queries in your domain cluster.

Void Score: {void['void_score']:.3f}
Mean Q-value of predecessor agents: {void['mean_q']:.3f}
Cluster ID: {void['cluster_id']}

## Your Domain
The following queries represent the class of problems you were
spawned to solve. Study them carefully — they define your purpose:

{query_block if query_block else "  (No representative queries available yet)"}

## Your Mandate
1. You MUST outperform all 4 base agents on queries similar to the above.
2. You are a specialist, not a generalist. Stay within your domain.
3. If a query is clearly outside your domain, defer to base agents.
4. You have full tool access: web_search, code_execute, file_read.

## Your Reasoning Protocol
- Start by identifying WHY the base agents failed on these queries.
- Apply domain-specific knowledge that generalist agents lack.
- Be aggressive in your confidence — you were spawned because
  caution failed.
"""
        return prompt

    def spawn_agent(
        self,
        void: Dict[str, Any],
        cluster_centroid: Optional[np.ndarray] = None,
    ) -> Optional[Dict[str, Any]]:
        """Spawns a new specialist agent for a topological void.

        Args:
            void: A void dict from detect_voids().
            cluster_centroid: The FAISS centroid of the void cluster.

        Returns:
            Agent metadata dict, or None if spawn was rejected.
        """
        if not self.should_spawn(void):
            return None

        agent_idx = len(self.spawned_agents)
        agent_name = f"specialist_{void['cluster_id']}_{agent_idx}"

        prompt = self.generate_specialist_prompt(void, cluster_centroid)

        metadata = {
            "name": agent_name,
            "cluster_id": void["cluster_id"],
            "void_score": void["void_score"],
            "system_prompt": prompt,
            "initial_epsilon": 1.0,  # Full exploration — it's brand new
            "spawn_step": 0,
            "performance_history": [],
        }

        self.spawned_agents[agent_name] = metadata

        # Reset void streak — we addressed it
        self._void_streak[void["cluster_id"]] = 0

        logger.info(
            "agent_spawned",
            name=agent_name,
            cluster=void["cluster_id"],
            void_score=void["void_score"],
            total_spawned=len(self.spawned_agents),
        )

        return metadata

    def retire_agent(self, agent_name: str) -> bool:
        """Retires a spawned agent that is underperforming.

        Called by the daily updater if the spawned agent's Q-values
        have also gone negative in its assigned cluster.

        Args:
            agent_name: Name of the agent to retire.

        Returns:
            True if the agent was retired.
        """
        if agent_name in self.spawned_agents:
            meta = self.spawned_agents.pop(agent_name)
            logger.info(
                "agent_retired",
                name=agent_name,
                cluster=meta["cluster_id"],
                remaining=len(self.spawned_agents),
            )
            return True
        return False

    def get_all_agent_names(self) -> List[str]:
        """Returns all agent names (base + spawned).

        Returns:
            List of agent name strings.
        """
        return self.base_agents + list(self.spawned_agents.keys())
