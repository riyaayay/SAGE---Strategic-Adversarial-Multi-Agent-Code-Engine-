import asyncio
import numpy as np
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from loguru import logger

from sage.core.aode import (
    Proposal, 
    topological_route, 
    lie_bracket_synthesis, 
    nash_refine
)
from sage.xai.trace import SageXAI

class SageState(TypedDict):
    """LangGraph State Schema."""
    query: str
    routed_agents: List[str]
    agent_outputs: Dict[str, Proposal]
    proposal: Optional[Proposal]
    cycle_history: List[Dict[str, Any]]
    xai_trace: List[str]
    final_answer: str
    divergence_index: float
    vram_peak_gb: float

def create_sage_graph(agents: Dict[str, Any]):
    """
    Constructs the SAGE/AODE StateGraph.
    """
    workflow = StateGraph(SageState)

    # 1. Ingest Node
    def ingest_node(state: SageState):
        logger.info(f"Ingesting query: {state['query']}")
        return {"xai_trace": ["Query ingested"]}

    # 2. Route Node
    def route_node(state: SageState):
        # In a real scenario, we'd fetch corpus vectors here
        # Mocking topological routing for the state machine
        void_indices, (b1, b2) = topological_route(
            np.random.randn(1024), # Mock query vec
            np.random.randn(100, 1024) # Mock corpus
        )
        return {
            "routed_agents": ["baseline", "orthogonal", "synthesizer"],
            "xai_trace": state["xai_trace"] + [f"Topological routing β1={b1}, β2={b2}"]
        }

    # 3. Debate Node (Parallel Execution)
    async def debate_node(state: SageState):
        logger.info("Executing parallel debate...")
        tasks = []
        for agent_name in state["routed_agents"]:
            agent = agents[agent_name]
            tasks.append(agent.generate(state["query"]))
        
        results = await asyncio.gather(*tasks)
        agent_outputs = {name: res for name, res in zip(state["routed_agents"], results)}
        
        return {
            "agent_outputs": agent_outputs,
            "xai_trace": state["xai_trace"] + ["Parallel debate complete"]
        }

    # 4. Synthesis Node (Lie Bracket)
    async def synth_node(state: SageState):
        out_A = state["agent_outputs"]["baseline"]
        out_B = state["agent_outputs"]["orthogonal"]
        out_C = state["agent_outputs"]["synthesizer"]
        
        # Non-Abelian synthesis via synthesizer agent
        synth_agent = agents["synthesizer"]
        
        # Compute ABC and ACB to find divergence
        # Simplified: we use the agent to do the actual text synthesis
        abc_text = await synth_agent.generate(f"Synthesize {out_A.text} and {out_B.text} then {out_C.text}")
        acb_text = await synth_agent.generate(f"Synthesize {out_A.text} and {out_C.text} then {out_B.text}")
        
        proposal, divergence = lie_bracket_synthesis(abc_text, acb_text, out_C, lambda x: x)
        
        return {
            "proposal": proposal,
            "divergence_index": divergence,
            "xai_trace": state["xai_trace"] + [f"Lie bracket divergence: {divergence:.4f}"]
        }

    # 5. Crucible Node (Nash Refinement)
    async def crucible_node(state: SageState):
        red_team = agents["red_team"]
        synth_agent = agents["synthesizer"]
        
        async def red_fn(text):
            return await red_team.generate(f"Attack this proposal: {text}")
            
        async def synth_fn(prop, attack):
            return await synth_agent.generate(f"Refine this: {prop.text} given attack: {attack.text}")

        final_proposal, history = await nash_refine(
            state["proposal"],
            red_fn,
            synth_fn
        )
        
        return {
            "proposal": final_proposal,
            "cycle_history": history,
            "xai_trace": state["xai_trace"] + [f"Nash equilibrium reached in {len(history)} cycles"]
        }

    # 6. Verify Node (XAI + PoW)
    def verify_node(state: SageState):
        xai = SageXAI()
        trace_log = xai.generate_proof_of_work(state["proposal"].text)
        return {
            "xai_trace": state["xai_trace"] + [f"Verification: {trace_log}"],
            "vram_peak_gb": 181.4 # Mocked for MI300X demo
        }

    # 7. Emit Node
    def emit_node(state: SageState):
        return {
            "final_answer": state["proposal"].text,
            "xai_trace": state["xai_trace"] + ["Final answer emitted"]
        }

    # Define the graph
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("route", route_node)
    workflow.add_node("debate", debate_node)
    workflow.add_node("synth", synth_node)
    workflow.add_node("crucible", crucible_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("emit", emit_node)

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "route")
    workflow.add_edge("route", "debate")
    workflow.add_edge("debate", "synth")
    workflow.add_edge("synth", "crucible")
    workflow.add_edge("crucible", "verify")
    workflow.add_edge("verify", "emit")
    workflow.add_edge("emit", END)

    return workflow.compile()
