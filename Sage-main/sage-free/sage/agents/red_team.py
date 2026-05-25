from sage.agents.base import VLLMAgent

class RedTeamAgent(VLLMAgent):
    """Mistral-7B FP16 (Approx 14 GB VRAM)."""
    def __init__(self):
        super().__init__(
            name="red_team",
            model_path="mistralai/Mistral-7B-Instruct-v0.3",
            quantization=None, # FP16
            gpu_memory_utilization=0.08,
            vram_gb=14.0
        )
