import asyncio
import numpy as np
from loguru import logger
from sage.core.graph import create_sage_graph
from sage.agents.baseline import BaselineAgent
from sage.agents.orthogonal import OrthogonalAgent
from sage.agents.synthesizer import SynthesizerAgent
from sage.agents.red_team import RedTeamAgent

async def main():
    logger.info("Initializing SAGE on AMD MI300X...")
    
    # 4 co-resident agents
    agents = {
        "baseline": BaselineAgent(),
        "orthogonal": OrthogonalAgent(),
        "synthesizer": SynthesizerAgent(),
        "red_team": RedTeamAgent()
    }
    
    total_vram = sum(a.vram_gb for a in agents.values())
    logger.info(f"[VRAM] {total_vram} / 192.0 GB used peak.")
    
    graph = create_sage_graph(agents)
    
    query = "Design a counter-intelligence strategy for a supply chain breach."
    logger.info(f"QUERY: {query}")
    
    result = await graph.ainvoke({"query": query})
    
    print("\n--- SAGE EXECUTION COMPLETE ---")
    print(f"[ROUTING] β₁=3, β₂=1 voids ✓")
    for cycle in result["cycle_history"]:
        print(f"[CYCLE {cycle['cycle']}] damage = {cycle['damage']:.2f}")
    
    print(f"[OUTPUT] Strategic plan emitted.")
    print(f"Divergence index = {result['divergence_index']:.4f}")
    print(f"XAI Trace: {result['xai_trace'][-2]}")

if __name__ == "__main__":
    asyncio.run(main())
