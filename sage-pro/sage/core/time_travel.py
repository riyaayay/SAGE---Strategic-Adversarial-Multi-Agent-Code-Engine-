"""
SAGE-PRO Time-Travel Engine
═════════════════════════════
Feature 3: Git-like branching of LangGraph execution states.

Every LangGraph node creates a checkpoint via MemorySaver.
This engine exposes those checkpoints as a navigable timeline:
  1. View full execution history
  2. Rewind to any prior state
  3. Branch from history to explore alternates
  4. Compare outputs across branches (diff)
"""

import copy
import hashlib
import structlog
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

logger = structlog.get_logger(__name__)


@dataclass
class TimelineNode:
    """A single checkpoint in the execution timeline."""
    checkpoint_id: str
    node_name: str
    timestamp: float
    thread_id: str
    branch_id: str = "main"
    parent_id: Optional[str] = None
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "node_name": self.node_name,
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "branch_id": self.branch_id,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "has_state": bool(self.state_snapshot),
        }


@dataclass
class Branch:
    """A named branch in the execution timeline."""
    branch_id: str
    name: str
    parent_branch: str
    fork_checkpoint_id: str
    created_at: float
    description: str = ""
    is_active: bool = True


class TimeTravelEngine:
    """Manages execution timeline, branching, and state restoration."""

    def __init__(self) -> None:
        self.nodes: Dict[str, TimelineNode] = {}
        self.branches: Dict[str, Branch] = {
            "main": Branch(
                branch_id="main", name="Main", parent_branch="",
                fork_checkpoint_id="", created_at=time.time(),
                description="Primary execution branch",
            )
        }
        self.thread_timelines: Dict[str, List[str]] = {}
        logger.info("time_travel_engine_initialized")

    def record_checkpoint(
        self, thread_id: str, node_name: str, state: Dict[str, Any],
        branch_id: str = "main", metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Records a new checkpoint after a LangGraph node completes."""
        ts = time.time()
        cid = hashlib.sha256(f"{thread_id}:{node_name}:{ts}".encode()).hexdigest()[:16]

        parent_id = None
        if thread_id in self.thread_timelines and self.thread_timelines[thread_id]:
            parent_id = self.thread_timelines[thread_id][-1]

        node = TimelineNode(
            checkpoint_id=cid, node_name=node_name, timestamp=ts,
            thread_id=thread_id, branch_id=branch_id, parent_id=parent_id,
            state_snapshot=self._sanitize_state(state), metadata=metadata or {},
        )
        self.nodes[cid] = node
        self.thread_timelines.setdefault(thread_id, []).append(cid)

        logger.info("checkpoint_recorded", checkpoint_id=cid, node=node_name)
        return cid

    def get_timeline(self, thread_id: str, branch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the ordered execution timeline for a thread."""
        cids = self.thread_timelines.get(thread_id, [])
        return [
            self.nodes[c].to_dict() for c in cids
            if c in self.nodes and (branch_id is None or self.nodes[c].branch_id == branch_id)
        ]

    def get_checkpoint_state(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Returns the full state snapshot for a checkpoint."""
        node = self.nodes.get(checkpoint_id)
        return copy.deepcopy(node.state_snapshot) if node else None

    def create_branch(self, name: str, fork_checkpoint_id: str, description: str = "") -> Branch:
        """Creates a new branch from a historical checkpoint."""
        if fork_checkpoint_id not in self.nodes:
            raise ValueError(f"Checkpoint {fork_checkpoint_id} not found")

        bid = hashlib.sha256(f"{name}:{fork_checkpoint_id}:{time.time()}".encode()).hexdigest()[:12]
        source = self.nodes[fork_checkpoint_id]
        branch = Branch(
            branch_id=bid, name=name, parent_branch=source.branch_id,
            fork_checkpoint_id=fork_checkpoint_id, created_at=time.time(),
            description=description,
        )
        self.branches[bid] = branch
        logger.info("branch_created", branch_id=bid, name=name, forked_from=fork_checkpoint_id)
        return branch

    def get_branches(self) -> List[Dict[str, Any]]:
        """Returns all branches."""
        return [{
            "branch_id": b.branch_id, "name": b.name,
            "parent_branch": b.parent_branch,
            "fork_checkpoint_id": b.fork_checkpoint_id,
            "created_at": b.created_at, "description": b.description,
            "is_active": b.is_active,
            "checkpoint_count": sum(1 for n in self.nodes.values() if n.branch_id == b.branch_id),
        } for b in self.branches.values()]

    def diff_checkpoints(self, cp_a: str, cp_b: str) -> Dict[str, Any]:
        """Compares two checkpoint states and returns the diff."""
        sa = self.get_checkpoint_state(cp_a) or {}
        sb = self.get_checkpoint_state(cp_b) or {}
        ka, kb = set(sa.keys()), set(sb.keys())

        changed = {}
        for k in (ka & kb):
            if sa[k] != sb[k]:
                changed[k] = {"before": str(sa[k])[:300], "after": str(sb[k])[:300]}

        return {
            "checkpoint_a": cp_a, "checkpoint_b": cp_b,
            "added": {k: sb[k] for k in (kb - ka)},
            "removed": {k: sa[k] for k in (ka - kb)},
            "changed": changed,
        }

    def rewind_to(self, thread_id: str, checkpoint_id: str) -> Dict[str, Any]:
        """Rewinds a thread's timeline to a specific checkpoint."""
        if checkpoint_id not in self.nodes:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        tl = self.thread_timelines.get(thread_id, [])
        if checkpoint_id not in tl:
            raise ValueError(f"Checkpoint doesn't belong to thread {thread_id}")

        idx = tl.index(checkpoint_id)
        self.thread_timelines[thread_id] = tl[:idx + 1]
        logger.info("timeline_rewound", thread=thread_id, target=checkpoint_id)
        return self.get_checkpoint_state(checkpoint_id) or {}

    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a JSON-serializable copy of the state."""
        safe: Dict[str, Any] = {}
        for key, value in state.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                safe[key] = value
            elif isinstance(value, (list, tuple)):
                safe[key] = [
                    (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)[:500])
                    for v in list(value)[:50]
                ]
            elif isinstance(value, dict):
                safe[key] = self._sanitize_state(value)
            else:
                safe[key] = f"<{type(value).__name__}>"
        return safe
