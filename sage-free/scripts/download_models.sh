#!/bin/bash
# Download models for SAGE
# Requires HF_TOKEN in .env

set -e

models=(
  "meta-llama/Meta-Llama-3-70B-Instruct"
  "Qwen/Qwen2.5-72B-Instruct"
  "microsoft/WizardLM-2-8x22B"
  "mistralai/Mistral-7B-Instruct-v0.3"
  "BAAI/bge-large-en-v1.5"
)

mkdir -p models

for model in "${models[@]}"; do
  echo "Downloading $model..."
  huggingface-cli download "$model" --local-dir "models/$(basename $model)"
done
