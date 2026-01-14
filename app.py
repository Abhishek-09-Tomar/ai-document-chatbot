# app.py
import streamlit as st
import os
from llm.generator import generate_answer, load_model  # now valid

from PyPDF2 import PdfReader

st.set_page_config(page_title="AI Document Chatbot", page_icon="🤖", layout="wide")
st.title("AI Document Chatbot")
st.write("Ask questions about your documents!")

# -----------------------------
# Sidebar: Upload documents
# -----------------------------
uploaded_files = st.sidebar.file_uploader(
    "Upload PDF or TXT files (optional):",
    type=["pdf", "txt"],
    accept_multiple_files=True
)

# -----------------------------
# Helper: Extract text from files
# -----------------------------
def extract_text_from_file(file):
    try:
        if file.type == "application/pdf":
            reader = PdfReader(file)
            text = ""
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"[Page {i+1}]\n{page_text}\n\n"
            return [{"text": text, "metadata": {"source": file.name}}]
        else:
            # plain txt
            content = file.getvalue().decode("utf-8")
            return [{"text": content, "metadata": {"source": file.name}}]
    except Exception as e:
        st.error(f"Error reading {file.name}: {e}")
        return []

# -----------------------------
# Process all uploaded files
# -----------------------------
docs = []
for file in uploaded_files:
    docs.extend(extract_text_from_file(file))

# -----------------------------
# User query input
# -----------------------------
user_input = st.text_area("Enter your question:", height=150)

if st.button("Get Answer"):
    if not user_input.strip():
        st.warning("Please enter a question!")
    else:
        with st.spinner("Generating answer..."):
            # Send user question + docs context to generator
            answer = generate_answer(user_input, docs)
            st.success("Answer:")
            st.write(answer)

# -----------------------------
# Optional: quick usage tip
# -----------------------------
st.sidebar.markdown(
    """
    **Usage Tips:**  
    - Upload one or multiple PDF/TXT documents.  
    - Ask questions in the text area and click "Get Answer".  
    - The chatbot answers based on uploaded documents.  
    - If no documents are uploaded, it answers general questions.
    """
)
