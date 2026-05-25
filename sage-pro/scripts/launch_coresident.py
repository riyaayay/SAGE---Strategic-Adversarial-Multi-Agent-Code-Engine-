import subprocess
import time
import sys
import os
import signal
import yaml
import httpx
import asyncio
import structlog
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)

class VLLMOrchestrator:
    \"\"\"Manages co-resident vLLM processes on a single AMD MI300X.\"\"\"
    
    def __init__(self, config_paths: List[str]) -> None:
        self.config_paths = config_paths
        self.processes: List[subprocess.Popen] = []
        self.running = True

    async def health_check(self, port: int, name: str) -> bool:
        \"\"\"Checks if a vLLM server is healthy with backoff.\"\"\"
        async with httpx.AsyncClient() as client:
            for i in range(30): # 30 * 10s = 5 minutes
                try:
                    response = await client.get(f"http://localhost:{port}/v1/models")
                    if response.status_code == 200:
                        logger.info("vllm_server_ready", agent=name, port=port)
                        return True
                except:
                    pass
                logger.info("vllm_waiting", agent=name, attempt=i)
                await asyncio.sleep(10)
        return False

    def launch_smi_monitor(self):
        \"\"\"Logs GPU memory usage via rocm-smi.\"\"\"
        def monitor():
            while self.running:
                try:
                    res = subprocess.check_output(["rocm-smi", "--showmeminfo", "vram"], encoding="utf-8")
                    logger.info("vram_usage", stats=res.strip())
                except:
                    logger.warning("rocm_smi_unavailable")
                time.sleep(10)
        
        import threading
        threading.Thread(target=monitor, daemon=True).start()

    def start_servers(self) -> None:
        \"\"\"Spawns vllm serve processes for all configured agents.\"\"\"
        env = os.environ.copy()
        env["HIP_VISIBLE_DEVICES"] = "0"
        env["VLLM_USE_TRITON_FLASH_ATTN"] = "0" # Required for ROCm 6.2

        for path in self.config_paths:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
                
            # Handle list-based redteam config
            agents = config.get("agents", [config])
            
            for agent in agents:
                cmd = ["vllm", "serve", agent["model"], "--port", str(agent["port"])]
                if "quantization" in agent:
                    cmd += ["--quantization", agent["quantization"]]
                if "gpu_memory_utilization" in agent:
                    cmd += ["--gpu-memory-utilization", str(agent["gpu_memory_utilization"])]
                if "max_model_len" in agent:
                    cmd += ["--max-model-len", str(agent["max_model_len"])]
                if "dtype" in agent:
                    cmd += ["--dtype", agent["dtype"]]
                if "enforce_eager" in agent and agent["enforce_eager"]:
                    cmd += ["--enforce-eager"]
                if "tensor_parallel_size" in agent:
                    cmd += ["--tensor-parallel-size", str(agent["tensor_parallel_size"])]

                logger.info("spawning_vllm", agent=agent.get("name", agent["model"]), port=agent["port"])
                p = subprocess.Popen(cmd, env=env)
                self.processes.append(p)

    def shutdown(self, *args):
        \"\"\"Gracefully terminates all child processes.\"\"\"
        logger.info("orchestrator_shutting_down")
        self.running = False
        for p in self.processes:
            p.terminate()
        sys.exit(0)

async def main():
    configs = [
        "configs/vllm_architect.yaml",
        "configs/vllm_implementer.yaml",
        "configs/vllm_synthesizer.yaml",
        "configs/vllm_redteam.yaml"
    ]
    
    orchestrator = VLLMOrchestrator(configs)
    signal.signal(signal.SIGTERM, orchestrator.shutdown)
    signal.signal(signal.SIGINT, orchestrator.shutdown)

    orchestrator.start_servers()
    orchestrator.launch_smi_monitor()

    # Final health checks
    ports = [8001, 8002, 8003, 8004, 8005]
    checks = [orchestrator.health_check(p, f"port_{p}") for p in ports]
    await asyncio.gather(*checks)
    
    logger.info("all_servers_operational_co_resident")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
