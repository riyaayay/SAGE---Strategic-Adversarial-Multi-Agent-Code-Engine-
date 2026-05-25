import subprocess
import time
from loguru import logger

def launch():
    logger.info("Launching SAGE Co-resident Engine...")
    
    # 1. Start FastAPI server in background
    server_process = subprocess.Popen(["python3", "-m", "sage.api.server"])
    
    # 2. Wait for warmup
    time.sleep(10) 
    
    # 3. Launch Gradio UI
    logger.info("Launching UI...")
    subprocess.run(["python3", "demos/app_gradio.py"])

if __name__ == "__main__":
    launch()
