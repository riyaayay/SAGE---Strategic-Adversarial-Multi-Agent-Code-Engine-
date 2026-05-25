#!/bin/bash
set -euo pipefail

# SAGE-PRO Cloud Bootstrap Script
# Target: Ubuntu 22.04 with ROCm 6.2 (TensorWave / Hot Aisle)

echo "🚀 Provisioning SAGE-PRO Environment..."

# 1. Update and install base deps
sudo apt-get update && sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3-pip

# 2. Install Docker (if missing)
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# 3. Configure ROCm Docker Runtime
echo "🔧 Configuring ROCm Docker Runtime..."
sudo usermod -aG docker $USER

# 4. Pull and Launch SAGE-PRO
if [ -d "Sage" ]; then
    cd Sage/sage-pro
    git pull
else
    git clone https://github.com/realruneett/Sage.git
    cd Sage/sage-pro
fi

# 5. Build and Launch
echo "🏗️  Building SAGE-PRO ROCm Image..."
sudo docker compose build

echo "✨ Launching SAGE-PRO..."
sudo docker compose up -d

echo "✅ SAGE-PRO is now running on http://$(curl -s ifconfig.me):8000"
echo "🌐 Dashboard available on http://$(curl -s ifconfig.me):7860"
