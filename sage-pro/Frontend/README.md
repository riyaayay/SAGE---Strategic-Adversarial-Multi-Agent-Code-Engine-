---
title: SAGE — Strategic Adversarial Generative Engine
emoji: 🧠
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: true
license: mit
---

# SAGE-PRO — Strategic Adversarial Generative Engine

Multi-agent AI system running on AMD Instinct MI300X with tier-based model routing.

## Tiers
- **Simple** — Direct response, ~0.2s
- **Medium** — Full pipeline, qwen2.5-coder:32b
- **Complex** — Adversarial debate, deepseek-r1:32b vs qwen2.5-coder:32b
- **Boardroom** — Full council with 72b model (say "boardroom:" to trigger)

## Demo Mode
Set `SAGE_MODE=demo` for zero-GPU demo on HF Spaces.
