#!/bin/bash
set -e

# SAGE-PRO Model Download Script
# Target: AMD MI300X Optimized AWQ Weights

MODELS=(
    "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
    "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4"
    "MaziyarPanahi/Mistral-Large-Instruct-2407-AWQ"
    "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
)

mkdir -p ./models

# Login if token is provided
if [ ! -z "${HF_TOKEN:-}" ]; then
    echo "Logging into Hugging Face..."
    huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
fi

for model in "${MODELS[@]}"; do
    echo "Downloading $model..."
    huggingface-cli download "$model" --local-dir "./models/$(basename $model)" --local-dir-use-symlinks False
done

echo "All SAGE-PRO models downloaded successfully."
