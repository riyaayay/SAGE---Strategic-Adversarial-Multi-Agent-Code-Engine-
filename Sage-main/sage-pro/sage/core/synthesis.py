"""
SAGE-PRO Non-Abelian Concept Synthesis
═══════════════════════════════════════
Implements the 3-agent nested Lie Bracket:

    [[P, R], V] ≠ [[P, V], R]

Three agents: P (Architect/design), R (Red-Team/threats), V (Implementer/code).

Branch ABC:  [P,R] → V   →  first merge design+threats, then implement
Branch ACB:  [P,V] → R   →  first implement from design, then attack

Both branches execute in parallel via asyncio.gather to maintain
the integrity of the divergence signal.
"""

import asyncio
import structlog
from typing import Tuple, Any, Dict, Optional

from sage.core.aode import lie_bracket_divergence

logger = structlog.get_logger(__name__)


async def parallel_branches(
    architect_spec: str,
    implementer: Any,
    red_team: Any,
    synthesizer: Any,
    red_team_pre: str,
    torsion_a: str,
    torsion_b: str,
    logit_bias_a: Optional[Dict[int, float]] = None,
    logit_bias_b: Optional[Dict[int, float]] = None,
) -> Tuple[str, str]:
    """Executes parallel 3-agent nested Lie bracket synthesis branches.

    This implements the non-abelian property of the AODE system:
        [[P, R], V] ≠ [[P, V], R]

    Branch ABC: [[P,R],V]
        1. Inner merge [P,R]: Synthesizer merges design (P) + threats (R)
        2. Outer [·,V]: Implementer implements from the merged spec

    Branch ACB: [[P,V],R]
        1. Inner [P,V]: Implementer implements from design (P) directly
        2. Outer [·,R]: Red-Team attacks the implementation, hardening it

    Both branches run in parallel via asyncio.gather.

    Args:
        architect_spec: The design spec from the Architect (P).
        implementer: The Implementer agent instance (V).
        red_team: The RedTeam agent instance (R).
        synthesizer: The Synthesizer agent instance.
        red_team_pre: Prior findings to bias the threat-first branch.
        torsion_a: Primary torsion nudge text for branch ABC.
        torsion_b: Secondary torsion nudge text for branch ACB.
        logit_bias_a: Logit bias dict for branch ABC torsion enforcement.
        logit_bias_b: Logit bias dict for branch ACB torsion enforcement.

    Returns:
        A tuple of (code_abc, code_acb).
    """
    if logit_bias_a is None:
        logit_bias_a = {}
    if logit_bias_b is None:
        logit_bias_b = {}

    logger.info("launching_parallel_synthesis_branches_3agent")

    async def branch_abc() -> str:
        """[[P,R],V] — Design+Threats first, then Implement."""
        # Step 1: Inner merge [P, R] — combine design with threats
        pr_merged = await synthesizer.merge(
            architect_spec,           # spec
            architect_spec,           # code_abc (design text)
            red_team_pre,             # code_acb (threat text)
            red_team_prior="",        # no prior needed for inner merge
        )
        logger.info("branch_abc_inner_merge_complete", merged_len=len(pr_merged))

        # Step 2: Outer [[P,R], V] — implement from the merged spec
        code_abc = await implementer.implement(pr_merged, torsion_a)
        logger.info("branch_abc_complete", code_len=len(code_abc))
        return code_abc

    async def branch_acb() -> str:
        """[[P,V],R] — Design+Implement first, then Attack."""
        # Step 1: Inner [P, V] — implement directly from design
        impl_text = await implementer.implement(architect_spec, torsion_b)
        logger.info("branch_acb_inner_impl_complete", impl_len=len(impl_text))

        # Step 2: Inner merge [P, V] — combine design with implementation
        pv_merged = await synthesizer.merge(
            architect_spec,           # spec
            architect_spec,           # code_abc (design text)
            impl_text,                # code_acb (implementation)
            red_team_prior="",
        )

        # Step 3: Outer [[P,V], R] — Red-Team attacks the merged result
        attack_result = await red_team.attack(pv_merged, architect_spec)
        logger.info("branch_acb_attack_complete",
                     findings_count=len(attack_result.get("security_findings", [])))

        # Extract hardened output from Red-Team analysis
        # Use the first security finding as the hardened perspective,
        # or fall back to the merged implementation
        if attack_result.get("security_findings"):
            code_acb = attack_result["security_findings"][0]
        else:
            code_acb = pv_merged

        logger.info("branch_acb_complete", code_len=len(code_acb))
        return code_acb

    # Launch both branches in true parallel
    results = await asyncio.gather(branch_abc(), branch_acb())
    return results[0], results[1]


async def synthesize(
    spec: str,
    code_abc: str,
    code_acb: str,
    red_team_findings: str,
    synthesizer: Any,
) -> Tuple[str, float]:
    """Merges divergent 3-agent branches into a single hardened solution.

    Computes the Lie Bracket divergence [ABC, ACB] to measure how much the
    ordering of agents affected the output, then merges both into a final
    Nash-stable artifact.

    Args:
        spec: Original design spec.
        code_abc: Branch ABC code ([[P,R],V]).
        code_acb: Branch ACB code ([[P,V],R]).
        red_team_findings: Findings from the Red-Team ensemble.
        synthesizer: The Synthesizer agent instance.

    Returns:
        A tuple of (final_code, divergence_index).
    """
    # Calculate Lie Bracket [ABC, ACB] — AST + Levenshtein structural diff
    div_index = lie_bracket_divergence(code_abc, code_acb)
    logger.info("lie_bracket_divergence_calculated", divergence=div_index)

    final_code = await synthesizer.merge(spec, code_abc, code_acb, red_team_findings)
    return final_code, div_index
