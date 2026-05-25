# Deployment Guide: AMD Developer Cloud

Follow these steps to deploy SAGE on an AMD Instinct MI300X instance.

## 1. Environment Setup

```bash
# Update ROCm drivers if necessary
sudo apt update && sudo apt upgrade -y
rocm-smi # Verify MI300X visibility
```

## 2. Model Preparation

```bash
git clone https://github.com/user/sage-aode
cd sage-aode
pip install -r requirements.txt

# Download models
export HF_TOKEN="your_token"
bash scripts/download_models.sh
```

## 3. Launch with Docker

```bash
docker compose build -f Dockerfile.rocm
docker compose up -d sage
```

## 4. Verification

```bash
# Run the MI300X demo
python3 demos/demo_sage.py

# Run the OOM contrast
python3 demos/demo_h100_simulation.py
```
