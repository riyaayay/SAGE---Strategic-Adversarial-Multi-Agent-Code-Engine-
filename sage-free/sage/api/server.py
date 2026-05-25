from fastapi import FastAPI, HTTPException
from loguru import logger
import uvicorn
import os

from sage.api.schemas import AODERequest, AODEResponse
from sage.core.graph import create_sage_graph
from sage.agents.baseline import BaselineAgent
from sage.agents.orthogonal import OrthogonalAgent
from sage.agents.synthesizer import SynthesizerAgent
from sage.agents.red_team import RedTeamAgent

# Initialize agents
logger.info("Initializing MI300X Agents...")
agents = {
    "baseline": BaselineAgent(),
    "orthogonal": OrthogonalAgent(),
    "synthesizer": SynthesizerAgent(),
    "red_team": RedTeamAgent()
}

app = FastAPI(title="SAGE x AODE API", version="0.1.0")
graph = create_sage_graph(agents)

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "hardware": "AMD MI300X detected"}

@app.get("/warmup")
async def warmup():
    logger.info("Warming up models...")
    return {"status": "warmed_up"}

@app.post("/v1/aode", response_model=AODEResponse)
async def aode_endpoint(request: AODERequest):
    logger.info(f"Received request: {request.query}")
    
    try:
        inputs = {"query": request.query}
        result = await graph.ainvoke(inputs)
        
        return AODEResponse(
            final_answer=result["final_answer"],
            divergence_index=result["divergence_index"],
            nash_cycles=len(result["cycle_history"]),
            xai_trace=result["xai_trace"],
            vram_peak_gb=result["vram_peak_gb"],
            cycle_history=result["cycle_history"]
        )
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
