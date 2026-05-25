# Hardware Necessity: Why MI300X?

SAGE-PRO's AODE reasoning requires high-fidelity, co-resident agents to maintain the "manifold integrity" of the parallel synthesis branches. Serializing these agents (swapping them in and out of VRAM) destroys the reasoning signal and increases latency by 10x.

## VRAM Accounting (Long-Context Mode)

| Agent | Model | VRAM (Quantized/FP16) | VRAM Fraction |
|-------|-------|-----------------------|---------------|
| Architect | Qwen2.5-32B | 22 GB | 11% |
| Implementer | DeepSeek-Lite | 14 GB | 7% |
| Synthesizer | Qwen2.5-72B | 46 GB | 24% |
| Red-Team | Ensemble (15B+Lite) | 34 GB | 18% |
| Vision Debugger | Llava-34B | 20 GB | 10% |
| KV Cache | Context (128K) | 48 GB | 25% |
| **TOTAL** | | **184 GB** | **95%** |

## The "H100 Barrier"

- **NVIDIA H100 (80GB)**: 80 GB total capacity.
- **SAGE-PRO Minimum**: 184 GB.
- **The Gap**: 104 GB.

Trying to run SAGE-PRO on an H100 results in a `HIP/CUDA out of memory` crash during the Synthesizer load phase. Only the **AMD MI300X (192GB)** has the HBM3 density to support this many co-resident, large-parameter models for high-speed adversarial reasoning.

![OOM Contrast Demo](figures/oom_contrast.gif)
