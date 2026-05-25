# SAGE AODE Fix Prompt — Claude Opus 4.6 (Extended Thinking)

---

## CONTEXT & MISSION

You are fixing the AODE (Adversarial Orthogonal Divergence Engine) implementation for
**SAGE-PRO**, a production-grade coding engine built for the **AMD Developer Hackathon
(MI300X)**. The engine must run fully on AMD ROCm with co-resident vLLM processes.

An audit identified **5 critical gaps** between the mathematical blueprint and the actual
code. Your task is to produce **complete, drop-in replacement files** for each broken
module. Do not produce partial diffs. Every file you return must be fully runnable.

**Before writing any code**, use your extended thinking to:
1. Re-read every file in the CURRENT CODE section carefully.
2. Map each gap to its root cause in the code.
3. Plan the minimal, cleanest fix for each gap without breaking other modules.
4. Only then write the final corrected files.

---

## THE 5 GAPS TO FIX (ordered by priority)

### GAP 1 — LangGraph nodes are stubs not wired to agents  `[CRITICAL]`

**Location:** `sage/core/graph.py`

**Problem:** Every node function returns a hardcoded literal. The `Architect`,
`Implementer`, `RedTeam`, and `Synthesizer` agent classes exist and are correct —
they are simply never called from the graph. The entire AODE pipeline is
architecturally hollow.

**Required fix:**
- The graph must accept a dependency-injected `agents` dict containing live instances
  of `Architect`, `Implementer`, `RedTeam`, and `Synthesizer`.
- Each node must call the correct agent method with the correct state fields.
- `route_node` → calls `CodeTopologyRouter.route(task, repo_files)`
- `architect_node` → calls `Architect.design(task, context_files)`
- `pre_attack_node` → calls `RedTeam.attack(initial_placeholder_code, architect_spec)`
- `parallel_branches_node` → calls `synthesis.parallel_branches(...)` with live agents
- `synthesize_node` → calls `synthesis.synthesize(...)` and stores `divergence_index`
- `crucible_node` → calls `crucible.crucible_loop(...)` with live agents and tools
- `verify_node` → calls tool functions (ruff, mypy, bandit) on `final_code`
- `emit_node` → assembles `SageResponse` from all state fields
- The `build_graph()` function must accept `agents: Dict` and `tools: Dict` params
  and use `functools.partial` or closures to inject them into each node.

---

### GAP 2 — Routing PH uses random noise; metric is inverted  `[CRITICAL]`

**Location:** `sage/core/routing.py`

**Problems (two bugs, one fix):**

**Bug A — Random vectors in PH:** In the `route()` method, the code builds
`neighborhood_vecs` using `np.random.randn(1, 384)`. This means the Betti number
computation is on pure random noise, destroying the topological signal entirely.

**Fix A:** After searching FAISS for nearest indices, retrieve the actual stored
embedding vectors from the FAISS index using `self.index.reconstruct(int(idx))` and
use those real vectors in `persistent_homology_features(...)`.

**Bug B — Argmin instead of argmax:** The blueprint specifies:
```
Target = argmax_i D(Q, A_i)   # farthest domain = maximum divergence
```
But FAISS HNSW returns *nearest* neighbors (minimum distance). The routing is
selecting the most *similar* domain, not the most *dissimilar* one.

**Fix B:** After retrieving the `k` nearest neighbors, invert the selection by
computing distances to ALL indexed vectors and returning the `k` with *maximum*
L2 distance from the query. Use `self.index.search(task_vec, self.index.ntotal)`
to get all distances, then `np.argsort(distances[0])[-k:][::-1]` to get the
farthest ones. Cap this at reasonable `ntotal` (use `min(self.index.ntotal, 500)`
if the index is large to avoid OOM).

---

### GAP 3 — Nash formula missing the `e^{−δt}` time-decay term  `[HIGH]`

**Location:** `sage/core/crucible.py`

**Problem:** The blueprint formula is:
```
Ψ_opt = argmax_{Ψ∈Blue} min_{C∈Red} [ Utility(Ψ) − Damage(C) × e^{−δt} ]
```
The `e^{−δt}` decay means that damage from early attacks is weighted more heavily
than damage from later attacks (the engine should converge). Currently `crucible.py`
computes flat damage with no temporal discount, and `delta` from hyperparams is
never read.

**Required fix:**
- Read `delta` from `hyperparams` (default `0.02`).
- After computing raw `damage` from `nash_damage(...)`, apply the discount:
  ```python
  import math
  discounted_damage = damage * math.exp(-delta * i)
  ```
  where `i` is the current cycle index (0-based).
- Use `discounted_damage` in `trajectory.append(...)` and in the convergence check
  `if discounted_damage < epsilon`.
- Store `discounted_damage` (not raw) in the `CrucibleCycle` record so the XAI
  trace reflects the true convergence signal.
- Log both `raw_damage` and `discounted_damage` in the structlog call.

---

### GAP 4 — Torsion applied at prompt level, not logit level  `[HIGH]`

**Location:** `sage/agents/base.py` + `sage/core/torsion.py`

**Problem:** The blueprint specifies:
```
P(token | context) = softmax(logits − Penalty(token ∈ Baseline_Tokens))
```
This is a logit-bias intervention at the vLLM inference layer. Currently torsion is
only a text string appended to the prompt — a much weaker and semantically noisier
signal.

**Required fix — two parts:**

**Part A — `base.py`:** Add an optional `logit_bias: Dict[int, float]` parameter
to both `complete()` and `stream()`. When provided, include it in the vLLM request
payload as `"logit_bias": logit_bias`. The vLLM OpenAI-compatible API supports this
field natively.

```python
async def complete(
    self,
    user_msg: str,
    extra_system: str = "",
    logit_bias: Optional[Dict[int, float]] = None   # NEW
) -> AgentResponse:
    payload = {
        ...existing fields...,
    }
    if logit_bias:
        payload["logit_bias"] = logit_bias           # NEW
```

**Part B — `torsion.py`:** Add a new function `torsion_to_logit_bias()` that
converts the selected torsion axis into a `logit_bias` dict. Since we cannot
enumerate all token IDs for a concept without a tokenizer, use a practical
approximation: map the torsion label string to a small set of
high-frequency proxy token IDs that represent the penalized concept. Use a
hardcoded `TORSION_PENALTY_MAP` dict that maps each of the 7 torsion axis labels
(from `torsion_suffixes.md`) to a list of `(token_id, penalty_float)` pairs
(use penalty values in range `[-5.0, -1.0]`). Make sensible token ID choices
(e.g., for `oop_vs_functional`, penalize common functional tokens like `lambda`=3,
`map`=8899, `filter`=3001; for `iteration_vs_recursion`, penalize `return`=7 with
the recursion penalty, etc. — these are illustrative; pick plausible GPT-2 vocab
IDs). Return a `Dict[int, float]`.

```python
def torsion_to_logit_bias(torsion_label: str) -> Dict[int, float]:
    """Converts a torsion axis label to a vLLM logit_bias dict."""
    ...
```

Then update `compute_torsion_suffix()` to also return the `logit_bias` dict
as a second return value (return a tuple `(suffix_text, logit_bias)`).

---

### GAP 5 — Lie bracket is 2-agent; blueprint requires 3-agent nesting  `[MEDIUM]`

**Location:** `sage/core/synthesis.py`

**Problem:** The blueprint specifies:
```
[[P, R], V] ≠ [[P, V], R]
```
Three agents: `P` (Architect/design), `R` (RedTeam/threats), `V` (Implementer/code).
The nesting means:
- Branch ABC: first merge (P, R) → then merge that result with V
- Branch ACB: first merge (P, V) → then merge that result with R

Currently `parallel_branches()` runs two `implementer.implement()` calls — there
is no nested merge, and the Architect and RedTeam are not contributing text to both
branches in the correct nested order.

**Required fix:**
- `parallel_branches()` must accept `architect`, `implementer`, `red_team`, and
  `synthesizer` as arguments.
- Branch ABC:
  1. `design_text = architect_spec` (P)
  2. `red_text = red_team_pre` (R)
  3. Inner merge: `pr_merged = await synthesizer.merge(spec, design_text, red_text)` → this is [P,R]
  4. Outer: `code_abc = await implementer.implement(pr_merged, torsion_a)` → [[P,R],V]
- Branch ACB:
  1. `design_text = architect_spec` (P)
  2. `impl_text = await implementer.implement(architect_spec, torsion_b)` (V)
  3. Inner merge: `pv_merged = await synthesizer.merge(spec, design_text, impl_text)` → [P,V]
  4. Outer: `code_acb = await red_team.attack(pv_merged, spec)` then use its output → [[P,V],R]
     (Since RedTeam.attack returns a dict, use `attack_result["security_findings"][0]`
     as the `code_acb` text, or make a dedicated `red_team.rewrite(code, spec)` method
     that returns a hardened code string — your choice, but be consistent.)
- Both branches must still be launched with `asyncio.gather` for true parallelism.
- Update the `synthesize()` function's docstring to reflect 3-agent nesting.

---

## CURRENT CODE (read carefully before writing anything)

### `sage/core/graph.py` (CURRENT — BROKEN)
```python
import structlog
from typing import TypedDict, List, Dict, Any, Tuple
from langgraph.graph import StateGraph, END
from sage.core.types import SageRequest, SageResponse, XAITrace, CrucibleCycle

logger = structlog.get_logger(__name__)

class SageState(TypedDict):
    request: SageRequest
    repo_files: List[Tuple[str, str]]
    task_route: List[Tuple[str, Tuple[int, int], float]]
    architect_spec: str
    red_team_pre: str
    code_abc: str
    code_acb: str
    final_code: str
    final_tests: str
    divergence_index: float
    cycle_history: List[CrucibleCycle]
    damage_trajectory: List[float]
    xai_trace: List[XAITrace]
    vram_peak_gb: float

async def ingest_node(state: SageState) -> Dict[str, Any]:
    logger.info("node_ingest_start")
    return {"xai_trace": [XAITrace(step_name="ingest", operator="io", divergence_signal=0.0, action_taken="Ingested context")]}

async def route_node(state: SageState) -> Dict[str, Any]:
    return {"task_route": [("main.py", (1, 100), 0.85)]}  # STUB

async def architect_node(state: SageState) -> Dict[str, Any]:
    return {"architect_spec": "Modular Design Spec v1"}  # STUB

async def pre_attack_node(state: SageState) -> Dict[str, Any]:
    return {"red_team_pre": "Initial threat identified: race condition potential."}  # STUB

async def parallel_branches_node(state: SageState) -> Dict[str, Any]:
    return {"code_abc": "def fast(): pass", "code_acb": "def secure(): pass"}  # STUB

async def synthesize_node(state: SageState) -> Dict[str, Any]:
    return {"final_code": "def hardened(): pass", "divergence_index": 0.12}  # STUB

async def crucible_node(state: SageState) -> Dict[str, Any]:
    return {"cycle_history": [], "damage_trajectory": [0.5, 0.1]}  # STUB

async def verify_node(state: SageState) -> Dict[str, Any]:
    return {"xai_trace": state["xai_trace"] + [XAITrace(step_name="verify", operator="oracle", divergence_signal=0.0, action_taken="Final verification passed")]}

async def emit_node(state: SageState) -> Dict[str, Any]:
    return {"vram_peak_gb": 184.2}  # STUB

def build_graph():
    workflow = StateGraph(SageState)
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("route", route_node)
    workflow.add_node("architect", architect_node)
    workflow.add_node("pre_attack", pre_attack_node)
    workflow.add_node("parallel_branches", parallel_branches_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("crucible", crucible_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("emit", emit_node)
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "route")
    workflow.add_edge("route", "architect")
    workflow.add_edge("architect", "pre_attack")
    workflow.add_edge("pre_attack", "parallel_branches")
    workflow.add_edge("parallel_branches", "synthesize")
    workflow.add_edge("synthesize", "crucible")
    workflow.add_edge("crucible", "verify")
    workflow.add_edge("verify", "emit")
    workflow.add_edge("emit", END)
    return workflow.compile()
```

---

### `sage/core/routing.py` (CURRENT — BROKEN)
```python
import faiss
import numpy as np
import structlog
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from sage.core.aode import persistent_homology_features

logger = structlog.get_logger(__name__)

class CodeTopologyRouter:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", index_dims: int = 384) -> None:
        self.embedder = SentenceTransformer(model_name)
        self.index = faiss.IndexHNSWFlat(index_dims, 32)
        self.file_map: List[str] = []
        logger.info("topology_router_initialized", model=model_name)

    def index_repository(self, repo_files: List[Tuple[str, str]]) -> None:
        if not repo_files:
            return
        contents = [content for _, content in repo_files]
        embeddings = self.embedder.encode(contents, convert_to_numpy=True)
        self.index.add(embeddings)
        self.file_map = [name for name, _ in repo_files]
        logger.info("repository_indexed", file_count=len(repo_files))

    def route(self, task: str, repo_files: List[Tuple[str, str]]) -> List[Tuple[str, Tuple[int, int], float]]:
        if self.index.ntotal == 0:
            self.index_repository(repo_files)
        task_vec = self.embedder.encode([task], convert_to_numpy=True)
        k = min(5, self.index.ntotal)
        distances, indices = self.index.search(task_vec, k)

        # BUG: Random noise fed to PH instead of real embeddings
        neighborhood_vecs = []
        for idx in indices[0]:
            if idx != -1:
                neighborhood_vecs.append(np.random.randn(1, 384))  # <-- BUG

        ph_features = persistent_homology_features(np.vstack(neighborhood_vecs))
        novelty_score = float(ph_features["b1"] + ph_features["b2"]) / 10.0

        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                results.append((
                    self.file_map[idx],
                    (1, 100),
                    float(1.0 - distances[0][i]) + novelty_score   # <-- BUG: nearest, not farthest
                ))
        return sorted(results, key=lambda x: x[2], reverse=True)
```

---

### `sage/core/crucible.py` (CURRENT — INCOMPLETE)
```python
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
    hyperparams: Dict[str, Any]
) -> Tuple[str, List[CrucibleCycle], List[float]]:
    current_code = initial_code
    history: List[CrucibleCycle] = []
    trajectory: List[float] = []
    max_cycles = hyperparams.get("max_cycles", 5)
    epsilon = hyperparams.get("epsilon", 0.01)
    # delta is in hyperparams but NEVER READ — BUG
    weights = hyperparams.get("damage_weights", {
        "ruff": 0.1, "mypy": 0.2, "bandit": 0.5,
        "semgrep": 0.4, "tests": 1.0, "complexity": 0.05
    })
    logger.info("crucible_loop_started", max_cycles=max_cycles)
    for i in range(max_cycles):
        ruff_findings = await tools["ruff"](current_code)
        mypy_findings = await tools["mypy"](current_code)
        bandit_findings = await tools["bandit"](current_code)
        attack_result = await red_team.attack(current_code, spec)
        test_report = await tools["sandbox"](current_code, attack_result["tests"])
        report = ToolReport(
            ruff=ruff_findings, mypy=mypy_findings, bandit=bandit_findings,
            tests_passed=test_report.tests_passed, coverage=test_report.coverage
        )
        damage = nash_damage(report.dict(), weights)   # flat damage — no decay
        trajectory.append(damage)
        cycle = CrucibleCycle(
            cycle_index=i, damage_score=damage,
            findings=report,
            refinement_prompt=attack_result["security_findings"][0] if attack_result["security_findings"] else ""
        )
        history.append(cycle)
        logger.info("crucible_cycle_complete", cycle=i, damage=damage)
        if damage < epsilon:  # convergence check uses raw damage — BUG
            logger.info("crucible_converged_early", cycle=i)
            break
        current_code = await synthesizer.merge(
            spec, current_code, current_code, red_team_prior=str(report.dict())
        )
    return current_code, history, trajectory
```

---

### `sage/agents/base.py` (CURRENT — MISSING logit_bias)
```python
import asyncio
import httpx
import structlog
import time
import hashlib
from typing import AsyncGenerator, Optional, List
from pathlib import Path
from sage.core.types import AgentResponse, XAITrace

logger = structlog.get_logger(__name__)

class VLLMAgent:
    def __init__(self, name, base_url, model_name, max_tokens=4096,
                 temperature=0.2, system_prompt_path=None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = ""
        if system_prompt_path:
            path = Path(system_prompt_path)
            if path.exists():
                self.system_prompt = path.read_text(encoding="utf-8")

    async def complete(self, user_msg: str, extra_system: str = "") -> AgentResponse:
        full_system = f"{self.system_prompt}\n\n{extra_system}".strip()
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_msg}
        ]
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False
            # logit_bias support MISSING
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            retries = 0
            max_retries = 3
            while retries <= max_retries:
                try:
                    start_time = time.time()
                    response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                    if response.status_code >= 500 and retries < max_retries:
                        retries += 1
                        await asyncio.sleep(2 ** retries)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    latency_ms = (time.time() - start_time) * 1000
                    prompt_hash = hashlib.md5(user_msg.encode()).hexdigest()[:8]
                    return AgentResponse(
                        agent_name=self.name,
                        content=content,
                        latency_ms=latency_ms,
                        thought_trace=[f"Prompt hash: {prompt_hash}"]
                    )
                except Exception as e:
                    if retries >= max_retries:
                        raise
                    retries += 1
                    await asyncio.sleep(2 ** retries)

    async def stream(self, user_msg: str) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            token = data["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except:
                            continue
```

---

### `sage/core/torsion.py` (CURRENT — PROMPT-LEVEL ONLY)
```python
import numpy as np
import structlog
from typing import Dict

logger = structlog.get_logger(__name__)

def compute_torsion_suffix(design_text: str, embedder, suffix_library: Dict[str, str]) -> str:
    design_vec = embedder.encode([design_text], convert_to_numpy=True)[0]
    suffixes = list(suffix_library.values())
    labels = list(suffix_library.keys())
    suffix_vecs = embedder.encode(suffixes, convert_to_numpy=True)
    dot_products = np.dot(suffix_vecs, design_vec)
    norms = np.linalg.norm(suffix_vecs, axis=1) * np.linalg.norm(design_vec)
    similarities = dot_products / (norms + 1e-9)
    ortho_scores = np.abs(similarities)
    best_idx = np.argmin(ortho_scores)
    selected_label = labels[best_idx]
    logger.info("torsion_suffix_selected", label=selected_label)
    return suffixes[best_idx]
    # Returns text only — no logit_bias
```

---

### `sage/core/synthesis.py` (CURRENT — 2-AGENT ONLY)
```python
import asyncio
import structlog
from typing import Tuple, Any
from sage.core.aode import lie_bracket_divergence

logger = structlog.get_logger(__name__)

async def parallel_branches(
    architect_spec: str,
    implementer: Any,
    red_team_pre: str,
    torsion_a: str,
    torsion_b: str
) -> Tuple[str, str]:
    logger.info("launching_parallel_synthesis_branches")
    tasks = [
        implementer.implement(architect_spec, torsion_a),
        implementer.implement(f"{architect_spec}\n\nPrior Issues: {red_team_pre}", torsion_b)
    ]
    results = await asyncio.gather(*tasks)
    return results[0], results[1]  # 2-agent only, no nested 3-agent bracket

async def synthesize(
    spec: str, code_abc: str, code_acb: str,
    red_team_findings: str, synthesizer: Any
) -> Tuple[str, float]:
    div_index = lie_bracket_divergence(code_abc, code_acb)
    logger.info("lie_bracket_divergence_calculated", divergence=div_index)
    final_code = await synthesizer.merge(spec, code_abc, code_acb, red_team_findings)
    return final_code, div_index
```

---

## SUPPORTING FILES (read-only context — do NOT modify)

### `sage/core/aode.py` (CORRECT — keep as-is)
Contains: `persistent_homology_features()`, `torsion_perpendicular()`,
`lie_bracket_divergence()`, `nash_damage()` — all mathematically correct.

### `sage/core/types.py` (CORRECT — keep as-is)
Contains: `ToolReport`, `AgentResponse`, `CrucibleCycle`, `XAITrace`,
`SageRequest`, `SageResponse` — all Pydantic models, frozen, correct.

### `sage/agents/architect.py` (CORRECT — keep as-is)
`Architect.design(task: str, context_files: List[str]) -> str`

### `sage/agents/implementer.py` (CORRECT — keep as-is)
`Implementer.implement(spec: str, torsion_suffix: str) -> str`

### `sage/agents/synthesizer.py` (CORRECT — keep as-is)
`Synthesizer.merge(spec, code_abc, code_acb, red_team_prior) -> str`

### `sage/agents/red_team.py` (CORRECT — keep as-is)
`RedTeam.attack(code: str, spec: str) -> Dict[str, Any]`
Returns: `{"tests": str, "security_findings": List[str], ...}`

### `configs/aode_hyperparams.yaml` (REFERENCE)
```yaml
epsilon: 0.05
delta: 0.02        # currently unused — must be read in crucible
max_cycles: 4
damage_weights:
  ruff: 0.1
  mypy: 0.2
  bandit: 0.5
  semgrep: 0.4
  tests: 1.0
  complexity: 0.05
embedding_model: "BAAI/bge-small-en-v1.5"
index_dims: 384
```

### `sage/prompts/torsion_suffixes.md` (REFERENCE — 7 axes)
```yaml
axes:
  - id: 1
    label: oop_vs_functional
  - id: 2
    label: iteration_vs_recursion
  - id: 3
    label: async_vs_sync
  - id: 4
    label: generic_vs_specialized
  - id: 5
    label: performance_vs_readability
  - id: 6
    label: memory_vs_cpu
  - id: 7
    label: defensive_vs_optimistic
```

---

## OUTPUT FORMAT

Return exactly **5 labelled code blocks**, one per gap. Use this structure:

```
### FILE: sage/core/graph.py
[complete file contents]

### FILE: sage/core/routing.py
[complete file contents]

### FILE: sage/core/crucible.py
[complete file contents]

### FILE: sage/agents/base.py
[complete file contents]

### FILE: sage/core/torsion.py
[complete file contents]

### FILE: sage/core/synthesis.py
[complete file contents]
```

### Constraints on every file you produce:
- Complete files only — no `# ... existing code ...` shortcuts
- All existing imports preserved; add new ones at the top
- All docstrings preserved and updated where the function signature changes
- Type hints on every function parameter and return value
- Must be compatible with: Python 3.11, `faiss-gpu`, `gudhi`, `langgraph>=0.1`,
  `vllm` OpenAI-compatible API, `sentence-transformers`, `structlog`, `pydantic v2`
- No breaking changes to the public API of any class or function (callers in
  `graph.py` and `scripts/launch_coresident.py` must still work)
- `build_graph()` signature changes to `build_graph(agents: Dict, tools: Dict)`
  — this is the only intentional API change; update all callers if referenced

---

## VERIFICATION CHECKLIST

After writing each file, mentally run through:

- [ ] `graph.py`: Is every node calling a real agent method? Is dependency injection
      done cleanly (closure or partial)? Does `SageState` have all needed fields?
- [ ] `routing.py`: Are real embedding vectors retrieved via `reconstruct()`? Is the
      argmax-farthest selection correct? Does PH get non-random input?
- [ ] `crucible.py`: Is `delta` read from hyperparams? Is `math.exp(-delta * i)`
      applied? Does the log show both raw and discounted damage?
- [ ] `base.py`: Is `logit_bias: Optional[Dict[int, float]] = None` in both
      `complete()` and `stream()`? Is it only included in the payload when not None?
- [ ] `torsion.py`: Does `TORSION_PENALTY_MAP` cover all 7 axis labels? Does
      `compute_torsion_suffix()` return `Tuple[str, Dict[int, float]]`? Does
      `torsion_to_logit_bias()` exist as a standalone function?
- [ ] `synthesis.py`: Is the 3-agent nesting [[P,R],V] and [[P,V],R] correctly
      implemented? Are both branches still launched with `asyncio.gather`?

---

*This is a hackathon submission for the AMD MI300X Developer Challenge.
All code runs on ROCm + vLLM. No PyTorch CUDA assumptions.*
