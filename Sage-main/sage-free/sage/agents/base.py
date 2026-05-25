import numpy as np
from vllm import LLM, SamplingParams
from sage.core.aode import Proposal
from loguru import logger
from typing import Optional

class VLLMAgent:
    """
    Base vLLM Agent wrapper optimized for AMD ROCm.
    """
    def __init__(
        self, 
        name: str, 
        model_path: str, 
        quantization: Optional[str] = "awq", 
        gpu_memory_utilization: float = 0.2, 
        max_model_len: int = 4096,
        vram_gb: float = 0.0
    ):
        self.name = name
        self.vram_gb = vram_gb
        logger.info(f"Initializing agent {name} with model {model_path} (GPU frac: {gpu_memory_utilization})")
        
        # enforce_eager=True is critical for ROCm to avoid CUDA graph VRAM spikes
        self.llm = LLM(
            model=model_path,
            quantization=quantization,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            enforce_eager=True,
            trust_remote_code=True
        )
        self.sampling_params = SamplingParams(temperature=0.7, max_tokens=1024)

    async def generate(self, prompt: str) -> Proposal:
        """
        Generates a response and returns a Proposal with a mock embedding.
        In production, the embedding would come from Layer 1 (BGE).
        """
        logger.info(f"Agent {self.name} generating...")
        
        # vLLM generate is blocking; in production, use vLLM's AsyncLLMEngine
        # Here we simulate the result for the architecture
        outputs = self.llm.generate([prompt], self.sampling_params)
        text = outputs[0].outputs[0].text
        
        # Mock embedding vector (1024-dim)
        vector = np.random.randn(1024)
        
        return Proposal(
            text=text,
            vector=vector,
            cycle=0,
            damage=1.0 if self.name == "red_team" else 0.0
        )
