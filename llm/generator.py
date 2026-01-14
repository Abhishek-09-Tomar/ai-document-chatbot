# generator.py
import requests
import json

# -----------------------------
# Ollama Configuration
# -----------------------------
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "gpt-oss:120b-cloud"   # YOUR INSTALLED MODEL
TOP_K_DOCS = 5


def load_model():
    """
    Ollama runs as a local service.
    This function is kept for compatibility with app.py.
    """
    return True


# -----------------------------
# Helper functions
# -----------------------------
def format_context(docs: list) -> str:
    """
    Formats retrieved documents into a single context string.
    """
    context_blocks = [
        f"[{d.get('metadata', {}).get('source', 'Doc')} | Page {d.get('metadata', {}).get('page', '?')}]\n"
        f"{d.get('text', '')}"
        for d in docs[:TOP_K_DOCS]
    ]
    return "\n\n".join(context_blocks)


def generate_answer(question: str, docs: list = None) -> str:
    """
    Generates an answer using the local Ollama model.
    """

    if docs:
        context = format_context(docs)
        prompt = f"""
You are a helpful document assistant.
Answer strictly using the context below.
If the answer is not present, say:
"Answer not found in the provided documents."

Context:
{context}

Question:
{question}

Answer:
"""
    else:
        prompt = question

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=300  # large model → allow more time
        )

        response.raise_for_status()
        return response.json().get("response", "").strip()

    except Exception as e:
        return f"Ollama generation error: {str(e)}"
