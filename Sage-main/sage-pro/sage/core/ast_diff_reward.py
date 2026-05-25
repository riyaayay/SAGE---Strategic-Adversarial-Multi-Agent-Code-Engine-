"""
SAGE-PRO Novel System 4: AST Diff Reward Crystallizer
══════════════════════════════════════════════════════
Deterministic, code-native reward signal computed from the
structural diff between the agent's FIRST code attempt and
the FINAL code that passes all tests.

Instead of relying on text-based correction detection ("you are wrong"),
this module computes a mathematically exact penalty from:
    1. AST Structural Edit Distance (tree-edit operations)
    2. Levenshtein Distance (character-level diff)
    3. Node-Type Change Ratio (what kinds of constructs changed)

The resulting "Code Delta Score" is a scalar [0, 1] that becomes
the ground-truth reward signal for the CTR Q-table.

  score = 1.0 → code was perfect on first attempt (no edits needed)
  score = 0.0 → code was completely rewritten (catastrophic failure)

Config: aode_hyperparams.yaml → ast_reward
"""

import ast
import difflib
import structlog
from typing import Dict, Any, List, Tuple, Set, Optional
from collections import Counter

logger = structlog.get_logger(__name__)


def _extract_node_types(code: str) -> Counter:
    """Extracts a frequency count of AST node types from Python code.

    Args:
        code: Python source code.

    Returns:
        Counter mapping node_type_name → count.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return Counter()

    return Counter(type(node).__name__ for node in ast.walk(tree))


def _count_ast_nodes(code: str) -> int:
    """Counts total AST nodes in Python code.

    Args:
        code: Python source code.

    Returns:
        Total node count.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    return sum(1 for _ in ast.walk(tree))


def _extract_function_signatures(code: str) -> List[str]:
    """Extracts function/method signatures from code.

    Args:
        code: Python source code.

    Returns:
        List of "funcname(arg1, arg2, ...)" strings.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    sigs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            sigs.append(f"{node.name}({', '.join(args)})")
    return sigs


def _extract_control_flow(code: str) -> List[str]:
    """Extracts control flow patterns (if/for/while/try).

    Args:
        code: Python source code.

    Returns:
        List of control flow node types encountered.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    flow_types = {ast.If, ast.For, ast.While, ast.Try, ast.With,
                  ast.AsyncFor, ast.AsyncWith}
    return [type(n).__name__ for n in ast.walk(tree) if type(n) in flow_types]


class ASTDiffRewardCrystallizer:
    """Computes deterministic code-native reward from AST structural diffs."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        """Initializes weights from config.

        Args:
            hyperparams: Full hyperparams dict (expects 'ast_reward' key).
        """
        cfg = hyperparams.get("ast_reward", {})

        # Weight for each component of the reward
        self.w_levenshtein: float = cfg.get("w_levenshtein", 0.25)
        self.w_node_ratio: float = cfg.get("w_node_ratio", 0.25)
        self.w_type_change: float = cfg.get("w_type_change", 0.20)
        self.w_signature_stability: float = cfg.get("w_signature_stability", 0.15)
        self.w_control_flow: float = cfg.get("w_control_flow", 0.15)

        logger.info(
            "ast_diff_reward_init",
            weights={
                "levenshtein": self.w_levenshtein,
                "node_ratio": self.w_node_ratio,
                "type_change": self.w_type_change,
                "sig_stability": self.w_signature_stability,
                "ctrl_flow": self.w_control_flow,
            },
        )

    def compute_levenshtein_score(
        self, first_code: str, final_code: str,
    ) -> float:
        """Computes normalized Levenshtein similarity.

        score = 1.0 if identical, 0.0 if completely different.

        Args:
            first_code: Agent's first attempt.
            final_code: Final passing code.

        Returns:
            Similarity score in [0, 1].
        """
        return difflib.SequenceMatcher(None, first_code, final_code).ratio()

    def compute_node_ratio_score(
        self, first_code: str, final_code: str,
    ) -> float:
        """Computes AST node count ratio similarity.

        Args:
            first_code: Agent's first attempt.
            final_code: Final passing code.

        Returns:
            Ratio score in [0, 1].
        """
        n1 = _count_ast_nodes(first_code)
        n2 = _count_ast_nodes(final_code)

        if n1 == 0 and n2 == 0:
            return 1.0
        if n1 == 0 or n2 == 0:
            return 0.0

        return min(n1, n2) / max(n1, n2)

    def compute_type_change_score(
        self, first_code: str, final_code: str,
    ) -> float:
        """Computes AST node type distribution similarity.

        Uses Jaccard similarity on the set of node types.

        Args:
            first_code: Agent's first attempt.
            final_code: Final passing code.

        Returns:
            Jaccard similarity in [0, 1].
        """
        types_a = set(_extract_node_types(first_code).keys())
        types_b = set(_extract_node_types(final_code).keys())

        if not types_a and not types_b:
            return 1.0
        if not types_a or not types_b:
            return 0.0

        intersection = types_a & types_b
        union = types_a | types_b
        return len(intersection) / len(union)

    def compute_signature_stability(
        self, first_code: str, final_code: str,
    ) -> float:
        """Checks how many function signatures survived unchanged.

        Args:
            first_code: Agent's first attempt.
            final_code: Final passing code.

        Returns:
            Proportion of signatures that survived in [0, 1].
        """
        sigs_a = set(_extract_function_signatures(first_code))
        sigs_b = set(_extract_function_signatures(final_code))

        if not sigs_a and not sigs_b:
            return 1.0
        if not sigs_a:
            return 0.0

        survived = sigs_a & sigs_b
        return len(survived) / len(sigs_a)

    def compute_control_flow_score(
        self, first_code: str, final_code: str,
    ) -> float:
        """Checks if control flow structure was preserved.

        Args:
            first_code: Agent's first attempt.
            final_code: Final passing code.

        Returns:
            Sequence similarity of control flow patterns in [0, 1].
        """
        flow_a = _extract_control_flow(first_code)
        flow_b = _extract_control_flow(final_code)

        if not flow_a and not flow_b:
            return 1.0

        return difflib.SequenceMatcher(None, flow_a, flow_b).ratio()

    def compute_code_delta_score(
        self,
        first_code: str,
        final_code: str,
    ) -> Dict[str, Any]:
        """Computes the full Code Delta Score.

        This is the deterministic, AST-based reward signal that replaces
        text-based correction detection. The score directly feeds the
        CTR engine's Q-table update.

        Args:
            first_code: The agent's first code attempt.
            final_code: The final code that passes all tests.

        Returns:
            Dict with component scores and the composite 'delta_score'.
        """
        lev = self.compute_levenshtein_score(first_code, final_code)
        node = self.compute_node_ratio_score(first_code, final_code)
        types = self.compute_type_change_score(first_code, final_code)
        sigs = self.compute_signature_stability(first_code, final_code)
        flow = self.compute_control_flow_score(first_code, final_code)

        composite = (
            self.w_levenshtein * lev
            + self.w_node_ratio * node
            + self.w_type_change * types
            + self.w_signature_stability * sigs
            + self.w_control_flow * flow
        )

        composite = max(0.0, min(1.0, composite))

        result = {
            "delta_score": composite,
            "levenshtein": lev,
            "node_ratio": node,
            "type_change": types,
            "signature_stability": sigs,
            "control_flow": flow,
            "first_code_nodes": _count_ast_nodes(first_code),
            "final_code_nodes": _count_ast_nodes(final_code),
        }

        logger.info(
            "code_delta_computed",
            delta_score=composite,
            levenshtein=f"{lev:.3f}",
            node_ratio=f"{node:.3f}",
            type_change=f"{types:.3f}",
            sig_stability=f"{sigs:.3f}",
            ctrl_flow=f"{flow:.3f}",
        )

        return result
