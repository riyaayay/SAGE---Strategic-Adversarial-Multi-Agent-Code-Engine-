from sage.agents.base import VLLMAgent

class OrthogonalAgent(VLLMAgent):
    """Qwen2.5-72B AWQ + LoRA torsion (Approx 45 GB VRAM)."""
    def __init__(self):
        # Note: In a real run, LoRA would be loaded via vLLM's lora_modules
        super().__init__(
            name="orthogonal",
            model_path="Qwen/Qwen2.5-72B-Instruct",
            quantization="awq",
            gpu_memory_utilization=0.24,
            vram_gb=45.0
        )
