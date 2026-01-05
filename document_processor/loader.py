import os
from pathlib import Path
from PyPDF2 import PdfReader

def _chunk(text: str, source_name: str, page_no: int, chunk_size: int, overlap: int):
    """
    Split text into overlapping chunks.
    """
    tokens = text.split()
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = " ".join(tokens[start:end])
        chunks.append({
            "text": chunk_text,
            "metadata": {
                "source": source_name,
                "page": page_no
            }
        })
        if end == len(tokens):
            break
        start += chunk_size - overlap
    return chunks

def load_documents(files, chunk_size=500, overlap=50):
    """
    Load multiple PDF or TXT files and split into chunks.
    Returns a list of dicts: {"text": ..., "metadata": {...}}
    """
    docs = []

    for file in files:
        name = file.name

        if name.lower().endswith(".pdf"):
            reader = PdfReader(file)
            for page_no, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():  # ignore empty pages
                    docs.extend(_chunk(text, name, page_no, chunk_size, overlap))
        elif name.lower().endswith(".txt"):
            text = file.read().decode("utf-8")
            if text.strip():
                docs.extend(_chunk(text, name, 1, chunk_size, overlap))
        else:
            # skip unsupported file types
            continue

    return docs
