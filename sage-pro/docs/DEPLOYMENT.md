# SAGE-PRO Deployment Guide

## Hardware Requirements
- **Accelerator**: 1x AMD Instinct MI300X (192GB HBM3).
- **Driver**: ROCm 6.2+.
- **Host**: Ubuntu 22.04 LTS.

## Quick Launch (Cloud One-Liner)
```bash
curl -sSL https://raw.githubusercontent.com/realruneett/Sage/main/scripts/cloud_bootstrap.sh | bash
```

## Manual Deployment (Docker)
1. Clone the repository:
   ```bash
   git clone https://github.com/realruneett/Sage.git
   cd Sage/sage-pro
   ```
2. Build the ROCm images for backend and frontend:
   ```bash
   docker compose build
   ```
3. Start the engine and the UI:
   ```bash
   docker compose up -d
   ```
4. **Access the IDE**: Open `http://<your-server-ip>:7860` in your browser.
   The headless API will run concurrently on port 8000.

*(Note: v3.0 requires `llava:34b` or equivalent loaded in Ollama for the Vision Debugging feature to function).*

## Troubleshooting

### vLLM Out of Memory
If you see `HIP out of memory`, ensure that `gpu_memory_utilization` values in `configs/vllm_*.yaml` sum to less than 0.95.

### vLLM Connectivity
Check server health:
```bash
curl http://localhost:8000/readyz
```
If not ready, check logs for the specific port (8001-8005).

### ROCm Version Pinning
SAGE-PRO is optimized for ROCm 6.2. Using older versions may cause performance degradation in Triton kernels.
