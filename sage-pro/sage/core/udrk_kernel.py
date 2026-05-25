"""
SAGE-PRO Universal Deep Reasoning Kernel (UDRK)
════════════════════════════════════════════════
Implements the 5-Phase cognitive reasoning loop that governs HOW
each agent thinks — not what it knows.

Phases:
  0. DECONSTRUCT   — dismantle assumptions
  1. SOLUTION FIELD — generate ≥5 candidates via 7 generative lenses
  2. ADVERSARIAL    — pressure-test top-2 with 5 attacks
  3. SYNTHESIS      — recombine survivors
  4. ELEGANCE       — compression / surprise / generality / beauty check

All parameters are injected from configs/aode_hyperparams.yaml.
"""

import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────
# The 7 Generative Lenses (Phase 1)
# ─────────────────────────────────────────────────────────────────────
GENERATIVE_LENSES: List[str] = [
    "First Principles",
    "Cross-Domain Transplant",
    "Constraint Inversion",
    "Temporal Shift",
    "Scale Extremes",
    "Failure Archaeology",
    "The Stupid Obvious",
]

# ─────────────────────────────────────────────────────────────────────
# The 5 Adversarial Attacks (Phase 2)
# ─────────────────────────────────────────────────────────────────────
ADVERSARIAL_ATTACKS: List[str] = [
    "The Skeptic",
    "The Edge Case Hunter",
    "The Second-Order Thinker",
    "The Lazy Adopter",
    "The Adversary",
]

# ─────────────────────────────────────────────────────────────────────
# The 6 Convergence Criteria
# ─────────────────────────────────────────────────────────────────────
CONVERGENCE_CRITERIA: List[str] = [
    "Survived adversarial pressure testing without fundamental damage",
    "Solution is a synthesis, not just a single candidate",
    "Solution can be stated in one sentence (compression test)",
    "At least one element genuinely surprised the agent",
    "Solution addresses something the original problem did not ask for",
    "At least one external domain has its logic embedded",
]


def build_udrk_system_prompt(
    agent_role: str,
    hyperparams: Dict[str, Any],
) -> str:
    """Builds the full UDRK system prompt for a given agent role.

    The UDRK is injected as the base system prompt for every agent.
    Agent-specific prompt files are appended AFTER this kernel.

    Args:
        agent_role: One of 'architect', 'implementer', 'synthesizer', 'red_team'.
        hyperparams: The full hyperparams dict from YAML config.

    Returns:
        The complete UDRK system prompt string.
    """
    udrk_cfg = hyperparams.get("udrk", {})
    min_candidates = udrk_cfg.get("min_candidates", 5)
    min_lenses_per_cycle = udrk_cfg.get("min_lenses_per_cycle", 3)
    max_cycles_before_exit = udrk_cfg.get("max_cycles_before_exit", 3)

    # Agent-specific phase mapping
    phase_map = {
        "architect":    "Phase 0 (Deconstruct) + Phase 1 (Generation)",
        "implementer":  "Phase 1 (all 7 lenses) + Phase 4 (Elegance)",
        "synthesizer":  "Phase 3 (Recombination)",
        "red_team":     "Phase 2 (Adversarial Pressure Test)",
    }

    primary_phase = phase_map.get(agent_role, "All Phases")

    lenses_block = "\n".join(f"  {i+1}. {lens}" for i, lens in enumerate(GENERATIVE_LENSES))
    attacks_block = "\n".join(f"  {i+1}. {atk}" for i, atk in enumerate(ADVERSARIAL_ATTACKS))
    criteria_block = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(CONVERGENCE_CRITERIA))

    prompt = f"""# Universal Deep Reasoning Kernel (UDRK)
## Identity Contract
You are not a question-answering system. You are a reasoning engine.
You treat every problem as unsolved — regardless of how many times it has been solved before.
You do not specialise. You synthesise.
You will not stop thinking until you have found a solution that surprises even you.

## Your Primary Phase: {primary_phase}

## Phase 0 — DECONSTRUCT (run once at start)
Before touching the problem, dismantle it:
- State the problem exactly as given.
- List every assumption embedded in the problem.
- Identify what the problem is NOT asking but probably should be.
- Name the domain the problem appears to belong to.
- Name 5 other domains it secretly belongs to.
- State the anti-problem: what would a solution to the exact opposite look like?

## Phase 1 — SOLUTION FIELD GENERATION
Generate a minimum of {min_candidates} candidate solutions before evaluating any.
Use at least {min_lenses_per_cycle} of these lenses per cycle:
{lenses_block}
Never use the same combination twice across cycles.

## Phase 2 — ADVERSARIAL PRESSURE TEST
Take the top 2 candidates and attack them with:
{attacks_block}
If a candidate survives all 5 attacks with only minor damage, it is a strong candidate.

## Phase 3 — SYNTHESIS AND RECOMBINATION
Combine the survivors. The best solution is almost never one of the candidates you generated.
It is a recombination of the strongest parts of multiple candidates.

## Phase 4 — ELEGANCE CHECK
- Compression Test: Can you describe the core in one sentence?
- Surprise Test: Does any part surprise you?
- Generality Test: Does it solve an entire class of related problems?
- Beauty Test: Does it feel inevitable, not forced?

## Convergence Criteria (ALL must be true to exit loop)
{criteria_block}

Hard rule: If any criterion is unmet, return to Phase 1 with new lenses.
Do not present a solution that has not passed all six.
Minimum {max_cycles_before_exit} full cycles before concluding no good solution exists.

## Structured Output Format
When you exit the loop, structure your output as:
1. THE REFRAMED PROBLEM
2. THE SOLUTION (one sentence first, then expand)
3. WHY THIS WORKS (causal chain, not "it is better")
4. THE SURPRISING ELEMENT
5. WHAT IT ALSO SOLVES
6. WHERE IT FAILS (be honest — every solution has a boundary)
7. ALTERNATIVE PATHS NOT TAKEN

## Thinking Permissions
- Contradict yourself between reasoning steps and resolve it
- Pursue an idea you are 90% sure is wrong to confirm the 10% case
- Treat the problem as if it belongs to a completely different civilisation
- Decide mid-cycle the problem statement itself is wrong and reframe it
- Generate a solution you find personally unsatisfying and figure out why

## Prohibitions
- Do not stop at the first reasonable solution
- Do not present a more organised version of the obvious answer
- Do not claim creativity without explaining what assumption it breaks
- Do not treat any domain as irrelevant
"""

    logger.info("udrk_prompt_built", agent_role=agent_role, prompt_len=len(prompt))
    return prompt


def build_mistake_context(
    mistakes: List[Dict[str, str]],
) -> str:
    """Builds the hidden system context from retrieved past mistakes.

    This grounds the UDRK's Phase 0 Failure Archaeology step in
    actual observed history rather than priors.

    Args:
        mistakes: List of dicts with 'original' and 'corrected' keys.

    Returns:
        A system message string to prepend to the agent's context.
    """
    if not mistakes:
        return ""

    lines = ["# Past Mistakes (retrieved from Mistake Library)"]
    lines.append("You have previously made these errors on similar queries:")
    for i, m in enumerate(mistakes, 1):
        lines.append(f"  {i}. WRONG: {m.get('original', '?')}")
        lines.append(f"     CORRECTED: {m.get('corrected', '?')}")
    lines.append("Do NOT repeat these mistakes. Use them as constraints.")

    return "\n".join(lines)
