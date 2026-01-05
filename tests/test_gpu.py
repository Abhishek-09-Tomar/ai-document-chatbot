# test/test_gpu.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"

# Check GPU availability
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU Name:", torch.cuda.get_device_name(0))

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Load 4-bit model on GPU
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    llm_int8_enable_fp32_cpu_offload=True
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    dtype=torch.float16
)

# Print model device
print("Model device:", next(model.parameters()).device)

# Quick generation test
prompt = "Hello! How are you?"
inputs = tokenizer(prompt, return_tensors="pt").to(next(model.parameters()).device)
outputs = model.generate(**inputs, max_new_tokens=20)
print("Generated:", tokenizer.decode(outputs[0], skip_special_tokens=True))
