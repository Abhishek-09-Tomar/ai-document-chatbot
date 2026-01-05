import streamlit as st
from dotenv import load_dotenv
import os
import numpy as np

from document_processor.loader import load_documents
from embeddings.embedder import EmbeddingEngine
from retrieval.faiss_store import VectorStore
from llm.generator import stream_answer, load_model_and_tokenizer
from utils.query_expansion import expand_query

# -----------------------------
# Load environment
# -----------------------------
load_dotenv()

# -----------------------------
# Streamlit page setup with favicon
# -----------------------------
favicon_path = "images/favicon.jpg"  # relative path to your favicon
st.set_page_config(
    page_title="AI Document Chatbot",
    page_icon=favicon_path,
    layout="centered"
)
st.title("AI Document Chatbot")

# -----------------------------
# Session State
# -----------------------------
if "store" not in st.session_state:
    st.session_state.store = None

# -----------------------------
# File uploader
# -----------------------------
files = st.file_uploader(
    "Upload documents (PDF or TXT)",
    type=["pdf", "txt"],
    accept_multiple_files=True
)

# -----------------------------
# Process documents
# -----------------------------
if st.button("Process Documents") and files:
    chunk_size = int(os.getenv("CHUNK_SIZE"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP"))

    docs = load_documents(files, chunk_size, chunk_overlap)
    st.success(f"Loaded {len(docs)} document chunks.")

    # Initialize embeddings and FAISS
    embedder = EmbeddingEngine()
    store = VectorStore(embedder, os.getenv("FAISS_PATH"))
    store.build_or_load(docs)

    st.session_state.store = store
    st.success("Documents processed and indexed successfully.")

# -----------------------------
# User query
# -----------------------------
query = st.chat_input("Ask a question")

if query and st.session_state.store:
    # Expand query for better retrieval
    expanded_queries = expand_query(query)

    # Retrieve top-K docs from FAISS + rerank
    retrieved_docs = []
    for q in expanded_queries:
        retrieved_docs.extend(
            st.session_state.store.search(
                q,
                int(os.getenv("TOP_K")),
                int(os.getenv("RERANK_TOP_K"))
            )
        )

    # -----------------------------
    # Stream answer in real-time
    # -----------------------------
    with st.chat_message("assistant"):
        placeholder = st.empty()
        final_answer = ""

        for token in stream_answer(query, retrieved_docs):
            final_answer += token
            placeholder.markdown(final_answer)
