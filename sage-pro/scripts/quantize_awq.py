import sys
import argparse
import structlog
from pathlib import Path

logger = structlog.get_logger(__name__)

def quantize_model(model_id: str, output_path: str):
    \"\"\"Quantizes a HuggingFace model to AWQ 4-bit using AutoAWQ.\"\"\"
    try:
        from awq import AutoAWQForCausalLM
        from transformers import AutoTokenizer
    except ImportError:
        logger.error("autoawq_not_installed")
        return

    logger.info("starting_quantization", model=model_id)
    
    # Quantization settings
    quant_config = {"zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM"}

    # Load model and tokenizer
    model = AutoAWQForCausalLM.from_pretrained(model_id, low_cpu_mem_usage=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

    # Quantize
    model.quantize(tokenizer, quant_config=quant_config)

    # Save quantized model
    model.save_quantized(output_path)
    tokenizer.save_pretrained(output_path)
    
    logger.info("quantization_complete", output=output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    
    if Path(args.output).exists():
        logger.info("skipping_quantization_already_exists")
    else:
        quantize_model(args.model, args.output)
