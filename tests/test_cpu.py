# test/test_cpu.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"

# Force CPU
device = "cpu"
print("Using device:", device)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Load full-precision model on CPU
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    dtype=torch.float32
)
model.to(device)

# Print model device
print("Model device:", next(model.parameters()).device)

# Quick generation test
prompt = "Hello! How are you?"
inputs = tokenizer(prompt, return_tensors="pt").to(device)
outputs = model.generate(**inputs, max_new_tokens=20)
print("Generated:", tokenizer.decode(outputs[0], skip_special_tokens=True))
