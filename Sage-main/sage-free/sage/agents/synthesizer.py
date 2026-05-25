from sage.agents.base import VLLMAgent

class SynthesizerAgent(VLLMAgent):
    """WizardLM-2-8x22B AWQ (Approx 80 GB VRAM)."""
    def __init__(self):
        super().__init__(
            name="synthesizer",
            model_path="microsoft/WizardLM-2-8x22B",
            quantization="awq",
            gpu_memory_utilization=0.42,
            vram_gb=80.0
        )
