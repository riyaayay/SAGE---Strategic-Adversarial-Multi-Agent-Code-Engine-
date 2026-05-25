"""
SAGE-PRO Novel System 2: Execution Trace Embeddings
═════════════════════════════════════════════════════
Embeds the SHAPE of code execution failures, not just query text.

Three embedding layers combined into a "Failure Fingerprint":
    1. AST Structural Embedding — tree shape of the code
    2. Stack Trace Embedding    — runtime failure signature
    3. Variable State Embedding — state at point of failure

Config: aode_hyperparams.yaml → execution_trace
"""

import ast
import hashlib
import struct
import numpy as np
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)


class ASTHasher:
    """Converts Python AST trees into fixed-dimensional numeric vectors
    using recursive structural hashing (the 'hashing trick')."""

    def __init__(self, embedding_dims: int = 128, max_depth: int = 6) -> None:
        self.dims = embedding_dims
        self.max_depth = max_depth
        self._node_vocab: Dict[str, int] = {}
        self._next_id = 1

    def _get_node_id(self, node_type: str) -> int:
        if node_type not in self._node_vocab:
            self._node_vocab[node_type] = self._next_id
            self._next_id += 1
        return self._node_vocab[node_type]

    def _walk_tree(self, node: ast.AST, depth: int = 0) -> List[int]:
        if depth >= self.max_depth:
            return []
        nid = self._get_node_id(type(node).__name__)
        sequence = [nid * 100 + depth]
        for child in ast.iter_child_nodes(node):
            sequence.extend(self._walk_tree(child, depth + 1))
        return sequence

    def hash_code(self, code: str) -> np.ndarray:
        """Hashes Python source into a fixed vector capturing structure."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return np.zeros(self.dims, dtype=np.float32)

        sequence = self._walk_tree(tree)
        if not sequence:
            return np.zeros(self.dims, dtype=np.float32)

        vec = np.zeros(self.dims, dtype=np.float32)
        for val in sequence:
            h1 = hashlib.md5(struct.pack("i", val)).hexdigest()
            bucket = int(h1[:8], 16) % self.dims
            sign = 1.0 if int(h1[8:16], 16) % 2 == 0 else -1.0
            vec[bucket] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class StackTraceHasher:
    """Converts Python stack traces into fixed-dimensional vectors."""

    def __init__(self, embedding_dims: int = 64) -> None:
        self.dims = embedding_dims

    def hash_trace(self, traceback_text: str) -> np.ndarray:
        vec = np.zeros(self.dims, dtype=np.float32)
        if not traceback_text:
            return vec

        lines = traceback_text.strip().split("\n")
        frame_lines = [l for l in lines if l.strip().startswith("File ")]
        vec[0] = len(frame_lines) / 20.0

        for frame in frame_lines[:10]:
            h = hashlib.md5(frame.encode()).hexdigest()
            bucket = int(h[:8], 16) % (self.dims - 10) + 5
            vec[bucket] += 1.0

        if lines:
            exc_type = lines[-1].strip().split(":")[0]
            h = hashlib.md5(exc_type.encode()).hexdigest()
            vec[int(h[:8], 16) % 5 + 1] = 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class VariableStateHasher:
    """Converts variable state snapshots into fixed-dimensional vectors."""

    def __init__(self, embedding_dims: int = 64) -> None:
        self.dims = embedding_dims

    def hash_state(self, variables: Dict[str, Any]) -> np.ndarray:
        vec = np.zeros(self.dims, dtype=np.float32)
        if not variables:
            return vec

        for name, value in list(variables.items())[:20]:
            h = hashlib.md5(name.encode()).hexdigest()
            bucket = int(h[:8], 16) % self.dims
            th = hashlib.md5(type(value).__name__.encode()).hexdigest()
            vec[bucket] += 1.0
            vec[int(th[:8], 16) % self.dims] += 0.5
            if isinstance(value, (int, float)):
                vec[bucket] += np.log1p(abs(value)) / 10.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class ExecutionTraceEmbedder:
    """Combines AST + stack trace + variable state into a single
    'Failure Fingerprint' for topology-aware failure routing."""

    def __init__(self, hyperparams: Dict[str, Any]) -> None:
        cfg = hyperparams.get("execution_trace", {})
        ast_dims = cfg.get("ast_embedding_dims", 128)
        trace_dims = cfg.get("trace_embedding_dims", 64)
        state_dims = cfg.get("state_embedding_dims", 64)
        self.combined_dims = ast_dims + trace_dims + state_dims

        self.ast_hasher = ASTHasher(ast_dims, cfg.get("hash_depth", 6))
        self.trace_hasher = StackTraceHasher(trace_dims)
        self.state_hasher = VariableStateHasher(state_dims)

        logger.info("execution_trace_embedder_init", dims=self.combined_dims)

    def compute_fingerprint(
        self, code: str, traceback_text: str = "",
        variables: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Computes the full Failure Fingerprint vector."""
        return np.concatenate([
            self.ast_hasher.hash_code(code),
            self.trace_hasher.hash_trace(traceback_text),
            self.state_hasher.hash_state(variables or {}),
        ])

    def compute_failure_distance(
        self, fp_a: np.ndarray, fp_b: np.ndarray,
    ) -> float:
        """L2 distance between two failure fingerprints."""
        return float(np.linalg.norm(fp_a - fp_b))
