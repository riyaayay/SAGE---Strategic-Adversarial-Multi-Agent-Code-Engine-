import gradio as gr
import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

SAGE_ENDPOINT = os.getenv("SAGE_ENDPOINT", "http://localhost:8000/v1/aode")

async def run_sage(query):
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(SAGE_ENDPOINT, json={"query": query})
            if response.status_code == 200:
                data = response.json()
                return (
                    data["final_answer"],
                    f"Divergence: {data['divergence_index']:.4f}\nCycles: {data['nash_cycles']}\nVRAM: {data['vram_peak_gb']} GB",
                    "\n".join(data["xai_trace"])
                )
            else:
                return "Error: " + response.text, "", ""
        except Exception as e:
            return f"Failed to connect to SAGE: {e}", "", ""

with gr.Blocks(title="SAGE × AODE Dashboard") as demo:
    gr.Markdown("# 🛡️ SAGE (Strategic Adversarial Generative Engine)")
    gr.Markdown("### Powered by AODE Reasoning Core | Target: AMD Instinct MI300X")
    
    with gr.Row():
        with gr.Column(scale=2):
            query_input = gr.Textbox(label="Strategic Query", placeholder="Enter your query here...", lines=3)
            submit_btn = gr.Button("Execute Reasoning Loop", variant="primary")
            
        with gr.Column(scale=1):
            stats_output = gr.Textbox(label="Engine Stats", interactive=False)
            
    with gr.Tabs():
        with gr.TabItem("Final Answer"):
            answer_output = gr.Markdown()
        with gr.TabItem("XAI Trace"):
            trace_output = gr.Code(language="markdown")

    submit_btn.click(
        fn=run_sage,
        inputs=[query_input],
        outputs=[answer_output, stats_output, trace_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
