import asyncio
import httpx
import time
from loguru import logger

async def send_prompt(client, query):
    start = time.time()
    try:
        response = await client.post("http://localhost:8000/v1/aode", json={"query": query})
        latency = time.time() - start
        return response.status_code, latency
    except Exception as e:
        return 500, time.time() - start

async def benchmark_concurrency(n=50):
    logger.info(f"Starting concurrency benchmark with {n} prompts...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [send_prompt(client, f"Strategic query {i}") for i in range(n)]
        results = await asyncio.gather(*tasks)
        
    latencies = [r[1] for r in results if r[0] == 200]
    if latencies:
        logger.info(f"Mean Latency: {sum(latencies)/len(latencies):.2f}s")
        logger.info(f"Success Rate: {len(latencies)/n * 100}%")
    else:
        logger.error("All requests failed.")

if __name__ == "__main__":
    asyncio.run(benchmark_concurrency(50))
