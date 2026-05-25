from sage.agents.base import VLLMAgent

class BaselineAgent(VLLMAgent):
    """Llama-3-70B AWQ (Approx 42 GB VRAM)."""
    def __init__(self):
        super().__init__(
            name="baseline",
            model_path="meta-llama/Meta-Llama-3-70B-Instruct",
            quantization="awq",
            gpu_memory_utilization=0.22,
            vram_gb=42.0
        )
