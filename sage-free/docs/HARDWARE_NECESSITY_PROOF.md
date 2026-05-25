# Hardware Necessity Proof

SAGE is designed to exceed the memory capacity of the NVIDIA H100 (80 GB) by requiring co-resident execution of four massive LLMs to maintain the **Non-Abelian property** of the reasoning loop.

## VRAM Consumption Breakdown

| Agent | Model | Quantization | GPU Fraction | Approx VRAM |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline** | Llama-3-70B | AWQ-4bit | 0.22 | 42 GB |
| **Orthogonal** | Qwen2.5-72B | AWQ-4bit | 0.24 | 45 GB |
| **Synthesizer** | WizardLM-2-8x22B | AWQ-4bit | 0.42 | 80 GB |
| **Red Team** | Mistral-7B | FP16 | 0.08 | 14 GB |
| **Total** | | | | **181 GB** |

## Conclusion

- **H100 (80 GB):** Can only fit the Synthesizer *or* the two smaller agents. Sequential swapping kills the "Parallel Debate" latency and breaks the Lie bracket timing.
- **AMD MI300X (192 GB):** Fits all four agents co-resident with ~11 GB buffer for KV-cache and activation.

### The Math of Divergence

The Lie bracket divergence $D = \| [A, B] \| = \| AB - BA \|$ requires that states $A$ and $B$ are accessible within the same temporal window. High latency from model swapping collapses $D \to 0$ due to state decay.
