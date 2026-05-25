# 🛡️ SAGE × AODE

**The first reasoning system that mathematically requires 192 GB HBM3.**

SAGE (Strategic Adversarial Generative Engine) is a high-stakes reasoning framework powered by the AODE (Adversarial Orthogonal Divergence Engine) core. It is purpose-built for the **AMD Instinct MI300X**, leveraging its massive 192 GB VRAM to run four heavyweight LLM agents co-resident.

![SAGE Architecture](docs/figures/sage_architecture.png)

## 🚀 The Hardware-Necessity Proof

SAGE is designed to OOM on NVIDIA H100 (80 GB) and require the MI300X (192 GB).

| Agent | Model | Quant | GPU Frac | VRAM |
| :--- | :--- | :--- | :--- | :--- |
| baseline | Llama-3-70B | awq | 0.22 | 42 GB |
| orthogonal | Qwen2.5-72B | awq | 0.24 | 45 GB |
| synthesizer | WizardLM-2-8x22B | awq | 0.42 | 80 GB |
| red_team | Mistral-7B | fp16 | 0.08 | 14 GB |
| **Total** | | | | **~181 GB** |

> [!IMPORTANT]
> Running these agents sequentially collapses the Lie bracket divergence. Co-residency is mathematically required for non-abelian synthesis.

## 🧠 AODE Operators

1.  **Persistent Homology:** $\beta_1, \beta_2$ routing to topological voids.
2.  **Riemann-Cartan Torsion:** Contextual warping via orthogonal shifts.
3.  **Non-Abelian Lie Bracket:** Synthesis where $[A, B] \neq [B, A]$.
4.  **Minimax Nash:** Iterative refinement against adversarial attacks.

## 🛠️ Quickstart (AMD MI300X)

```bash
git clone https://github.com/user/sage-aode
cd sage-aode
docker compose up -d sage

# Run the primary demo
python demos/demo_sage.py

# Prove hardware necessity (Expected OOM)
python demos/demo_h100_simulation.py

# Access API
curl -X POST http://localhost:8000/v1/aode -d '{"query": "..."}'
```

## 📊 OOM Contrast

![OOM Contrast](docs/figures/oom_contrast.gif)

## 📄 License

MIT © 2026 SAGE Contributors
