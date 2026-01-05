import os
import torch
from dotenv import load_dotenv
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TextIteratorStreamer,
    BitsAndBytesConfig
)
from threading import Thread

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()
MODEL_NAME = os.getenv("LLM_MODEL")
DEVICE_PREF = os.getenv("LLM_DEVICE", "cuda")  # "cuda" or "cpu"

if not MODEL_NAME:
    raise RuntimeError("LLM_MODEL is not set in .env")

# -----------------------------
# Helper: Load model + tokenizer safely
# -----------------------------
def load_model_and_tokenizer(model_name: str, device_preference="cuda"):
    """
    Dynamically loads model + tokenizer with safe 4-bit CPU offload if needed.
    Returns: model, tokenizer, device
    """
    device = device_preference if device_preference=="cuda" and torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    if device == "cuda":
        # 4-bit quantized model with CPU offload
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            llm_int8_enable_fp32_cpu_offload=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            dtype=torch.float16  # ✅ replaces deprecated torch_dtype
        )
    else:
        # CPU-only full precision
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float32  # ✅ replaces deprecated torch_dtype
        )

    model.eval()
    return model, tokenizer, device

# -----------------------------
# Load model at startup
# -----------------------------
model, tokenizer, device = load_model_and_tokenizer(MODEL_NAME, DEVICE_PREF)

# -----------------------------
# Constants
# -----------------------------
MAX_CONTEXT_TOKENS = tokenizer.model_max_length
MAX_NEW_TOKENS = 256
TOP_K_DOCS = 5

# -----------------------------
# Helper: trim context to token limit
# -----------------------------
def trim_to_token_limit(text: str, max_tokens: int) -> str:
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if len(tokens) <= max_tokens:
        return text
    return tokenizer.decode(tokens[-max_tokens:])

# -----------------------------
# Stream answer generator
# -----------------------------
def stream_answer(question: str, docs: list):
    """
    Generate answer from documents in a streaming fashion.
    Yields tokens as they are generated for real-time streaming.
    """
    context_blocks = [
        f"[{d['metadata'].get('source','Doc')} | Page {d['metadata'].get('page','?')}]\n{d['text']}"
        for d in docs[:TOP_K_DOCS]
    ]
    raw_context = "\n\n".join(context_blocks)

    prompt = f"""You are a helpful document assistant.
Answer strictly from the context. If not found, say so.

Context:
{raw_context}

Question:
{question}

Answer:"""

    # Trim prompt to fit model max tokens
    available_tokens = MAX_CONTEXT_TOKENS - MAX_NEW_TOKENS - 50
    prompt = trim_to_token_limit(prompt, available_tokens)

    # Tokenize inputs
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    # Setup streaming
    streamer = TextIteratorStreamer(tokenizer, skip_special_tokens=True)
    thread = Thread(
        target=model.generate,
        kwargs=dict(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
            streamer=streamer,
            eos_token_id=tokenizer.eos_token_id
        ),
    )
    thread.start()

    # Yield tokens in real-time
    for token in streamer:
        yield token
