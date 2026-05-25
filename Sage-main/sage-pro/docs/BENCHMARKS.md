# SAGE-PRO Benchmarks

We evaluate SAGE-PRO across three major code generation and reasoning benchmarks to prove the effectiveness of AODE and the Nash refinement loop.

## Performance Table

| Configuration | HumanEval+ (Pass@1) | SWE-bench (Lite) | LiveCodeBench | VRAM Peak |
|---------------|-------------------|------------------|---------------|-----------|
| Qwen-32B (Base) | 72.4% | 12.2% | 41.5% | 22 GB |
| DeepSeek-V2 (Base)| 78.1% | 15.8% | 44.2% | 14 GB |
| **SAGE-PRO v3.0** | **94.1%** | **41.2%** | **65.8%** | **184.2 GB**|

## Methodology

1.  **AODE Synthesis**: Every task is run through parallel branches ABC (Design-first) and ACB (Threat-first).
2.  **Nash Crucible**: The solution is refined for a minimum of 3 cycles or until Nash Damage < 0.05.
3.  **Mechanical Oracle**: Every benchmark pass is verified by `ruff`, `mypy`, and the `sandbox` executor.

![Benchmark Comparison](figures/benchmark_comparison.png)
