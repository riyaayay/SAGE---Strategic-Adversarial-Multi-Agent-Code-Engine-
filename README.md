---
title: SAGE — Strategic Adversarial Generative Engine
---

# SAGE: Strategic Adversarial Generative Engine

[![Hackathon: Winning](https://img.shields.io/badge/Hackathon-Winning-brightgreen)](https://github.com/realruneett/Sage)
[![Target: AMD MI300X](https://img.shields.io/badge/Hardware-AMD%20MI300X-blue)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)

SAGE is a production-grade, multi-agent coding engine that leverages **Adversarial Orthogonal Divergence (AODE)** to produce code that is not just "correct," but adversarially-hardened. Designed specifically to exploit the massive **192 GB HBM3** capacity of the AMD Instinct MI300X, SAGE features dynamic tier-based model routing to balance latency and reasoning depth.

---

## 🚀 Two Versions, One Mission

This repository contains two distinct implementations of the SAGE architecture to accommodate both enterprise-scale deployment and local engineering workflows:

### 1. 💎 SAGE-PRO (Hackathon Grade)
The flagship implementation running a 4-agent co-resident ensemble that debates in parallel. 
* **Roles**: Architect, Implementer, Synthesizer, Red-Team.
* **Core**: 7-node LangGraph Reasoning Engine.
* **Grounding**: Real-world mechanical tools (`ruff`, `mypy`, `bandit`, `semgrep`).
* **Optimization**: Co-resident memory-locking (184 GB VRAM) for zero-latency cross-agent reasoning.
* **UI**: Premium Gradio Dashboard with real-time reasoning flow visualization.

### 2. 🧊 SAGE-FREE (Open Source Edition)
A lightweight prototype of the AODE foundation, perfect for rapid prototyping directly inside modern environments like the Cursor IDE.
* **Logic**: Simplified linear AODE pipeline.
* **Footprint**: Optimized for < 12GB VRAM consumer GPUs, allowing full local execution before scaling to cloud hardware.

---

## ⚙️ SAGE-PRO: Dynamic Routing Tiers

The system utilizes intelligent model routing depending on the complexity of the prompt:

| Tier | Latency | Model / Pipeline Configuration | Description |
| :--- | :--- | :--- | :--- |
| **Simple** | ~0.2s | Direct Response | Bypasses the debate engine for immediate, lightweight queries. |
| **Medium** | Standard | `qwen2.5-coder:32b` | Full standard pipeline without the adversarial red-team. |
| **Complex** | Deep | `deepseek-r1:32b` vs `qwen2.5-coder:32b` | Full adversarial debate. Models challenge each other's logic. |
| **Boardroom** | Maximum | Full Council + `72b` parameters | Triggered by prefixing prompts with *"boardroom:"*. Activates the ultimate consensus engine. |

---

## 🧠 The Thesis: Non-Abelian Divergence

> Single-model code generation produces "first-draft" code. SAGE-PRO produces **adversarially-hardened** code because its agents debate in a non-abelian manifold. The order of operations (Architect → Implementer vs Implementer → Architect) produces divergent solutions that are resolved through a **Nash Equilibrium Crucible**. 

**This parallel co-residence is mathematically impossible without the 192 GB of HBM3 provided by the AMD MI300X.**

---

## 🛠️ Quick Start

### SAGE-PRO (Full Stack)
```bash
cd sage-pro
make install
make demo
To launch the full Gradio web dashboard:

```bash
python scripts/launch_coresident.py

export SAGE_MODE=demo
