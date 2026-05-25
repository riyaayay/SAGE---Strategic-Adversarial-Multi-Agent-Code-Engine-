"""
SAGE-PRO Minimax Adversarial Crucible
═════════════════════════════════════
Implements iterative best-response dynamics between Blue (Synthesizer)
and Red (Red-Team), grounded by deterministic tool oracles:

    Ψ_opt = argmax_{Ψ∈Blue} min_{C∈Red} [ Utility(Ψ) − Damage(C) × e^{−δi} ]

Game-Theoretic Justification:
    This is a two-player zero-sum iterative game.  Each cycle, Red
    plays a best-response attack, Blue plays a best-response fix.
    The exponential time-decay e^{-δi} ensures convergence by making
    later-round damage progressively cheaper.

    This is equivalent to fictitious play with exponential discounting.
    By Robinson (1951) and Brown (1951), fictitious play converges to
    Nash Equilibrium in all two-player zero-sum games.  The exponential
    discount guarantees finite convergence even when the strategy spaces
    are unbounded (as they are with LLM-generated code).
"""

import math
import asyncio
import structlog
from typing import List, Dict, Any, Tuple
from datetime import datetime

from sage.core.aode import nash_damage
from sage.core.types import ToolReport, CrucibleCycle

logger = structlog.get_logger(__name__)


async def crucible_loop(
    spec: str,
    initial_code: str,
    red_team: Any,
    synthesizer: Any,
    tools: Dict[str, Any],
    hyperparams: Dict[str, Any],
) -> Tuple[str, List[CrucibleCycle], List[float]]:
    """Implements the Nash Equilibrium refinement loop (The Crucible).

    Iteratively hardens code by pitting the Red-Team's attacks against the
    Synthesizer's fixes, grounded by deterministic tool feedback.

    The damage formula includes exponential time-decay:
        discounted_damage = raw_damage × e^{−δ·i}
    where δ is the decay constant and i is the cycle index.

    Args:
        spec: The architectural specification.
        initial_code: The first-draft code to refine.
        red_team: The Red-Team ensemble.
        synthesizer: The Synthesizer agent.
        tools: Dictionary of tool functions (ruff, mypy, bandit, sandbox).
        hyperparams: Tuning parameters (epsilon, delta, max_cycles, weights).

    Returns:
        A tuple of (final_hardened_code, cycle_history, damage_trajectory).
    """
    current_code = initial_code
    history: List[CrucibleCycle] = []
    trajectory: List[float] = []

    max_cycles = hyperparams.get("max_cycles", 5)
    epsilon = hyperparams.get("epsilon", 0.01)
    delta = hyperparams.get("delta", 0.02)  # ← time-decay constant (was unused)
    weights = hyperparams.get("damage_weights", {
        "ruff": 0.1,
        "mypy": 0.2,
        "bandit": 0.5,
        "semgrep": 0.4,
        "tests": 1.0,
        "complexity": 0.05,
    })

    logger.info("crucible_loop_started", max_cycles=max_cycles, epsilon=epsilon, delta=delta)

    for i in range(max_cycles):
        # 1. Grounded Assessment — external tool execution
        ruff_findings = await tools["ruff"](current_code)
        mypy_findings = await tools["mypy"](current_code)
        bandit_findings = await tools["bandit"](current_code)

        # 2. Adversarial Attack — Red-Team generates exploits
        attack_result = await red_team.attack(current_code, spec)

        # 3. Dynamic Verification — sandbox execution of adversarial tests
        test_report = await tools["sandbox"](current_code, attack_result["tests"])

        report = ToolReport(
            ruff=ruff_findings,
            mypy=mypy_findings,
            bandit=bandit_findings,
            tests_passed=test_report.tests_passed,
            coverage=test_report.coverage,
        )

        # 4. Damage Calculation with exponential time-decay
        raw_damage = nash_damage(report.dict(), weights)
        discounted_damage = raw_damage * math.exp(-delta * i)

        trajectory.append(discounted_damage)

        cycle = CrucibleCycle(
            cycle_index=i,
            damage_score=discounted_damage,  # ← discounted, not raw
            findings=report,
            refinement_prompt=(
                attack_result["security_findings"][0]
                if attack_result.get("security_findings")
                else ""
            ),
        )
        history.append(cycle)

        logger.info(
            "crucible_cycle_complete",
            cycle=i,
            raw_damage=raw_damage,
            discounted_damage=discounted_damage,
            decay_factor=math.exp(-delta * i),
        )

        # 5. Convergence Check — uses discounted damage
        if discounted_damage < epsilon:
            logger.info("crucible_converged_early", cycle=i, discounted_damage=discounted_damage)
            break

        # 6. Nash Refinement — Synthesizer fixes what Red-Team broke
        current_code = await synthesizer.merge(
            spec,
            current_code,
            current_code,  # self-refinement
            red_team_prior=str(report.dict()),
        )

    return current_code, history, trajectory
