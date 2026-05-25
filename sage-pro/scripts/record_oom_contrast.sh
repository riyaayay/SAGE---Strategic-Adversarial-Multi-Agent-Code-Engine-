#!/bin/bash
set -euo pipefail

# SAGE-PRO OOM Contrast Recorder
# Generates the 'H100 Failure' proof GIF

echo "🎥 Recording OOM Contrast Demo..."

mkdir -p docs/figures

# Record the simulation failure
# We use asciinema to capture the terminal output
if command -v asciinema &> /dev/null; then
    asciinema rec docs/figures/h100_oom.cast --overwrite -c "python3 demos/demo_h100_simulation.py --memory-cap-gb 80"
    
    # Convert to GIF using agg (asciinema-gen-gif)
    if command -v agg &> /dev/null; then
        agg docs/figures/h100_oom.cast docs/figures/oom_contrast.gif
        echo "✅ GIF generated at docs/figures/oom_contrast.gif"
    else
        echo "⚠️  'agg' not found. Skipping GIF conversion."
    fi
else
    echo "⚠️  'asciinema' not found. Skipping recording."
    # Fallback: just run it
    python3 demos/demo_h100_simulation.py --memory-cap-gb 80 || true
fi
