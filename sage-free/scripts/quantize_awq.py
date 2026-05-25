from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer
import sys

def quantize(model_path, save_path):
    print(f"Quantizing {model_path} to AWQ 4-bit...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoAWQForCausalLM.from_pretrained(model_path, trust_remote_code=True)
    
    quant_config = {"zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM"}
    model.quantize(tokenizer, quant_config=quant_config)
    
    model.save_quantized(save_path)
    print(f"Saved to {save_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python quantize_awq.py <model_path> <save_path>")
    else:
        quantize(sys.argv[1], sys.argv[2])
