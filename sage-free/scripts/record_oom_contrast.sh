#!/bin/bash
# Record OOM contrast via asciinema

echo "Starting OOM Contrast Recording..."

# Create a tmux session
tmux new-session -d -s sage_demo

# Pane 1: MI300X Success
tmux send-keys -t sage_demo "python3 demos/demo_sage.py" C-m

# Split and Pane 2: H100 OOM
tmux split-window -h -t sage_demo
tmux send-keys -t sage_demo "python3 demos/demo_h100_simulation.py" C-m

tmux attach-session -t sage_demo
