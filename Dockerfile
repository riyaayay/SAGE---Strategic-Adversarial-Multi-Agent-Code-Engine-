# SAGE-PRO Deployment Image for AMD MI300X (ROCm)
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy SAGE-PRO source
COPY app.py .

# Environment
ENV SAGE_MODE=pro
ENV ROCM_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
ENV HSA_OVERRIDE_GFX_VERSION=9.4.2

EXPOSE 7860

CMD ["python", "app.py"]
