---
title: AI Document Chatbot
emoji: 📄
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# AI document chatbot

Upload PDFs or UTF-8 text files, ask follow-up questions, and inspect the source passages behind each answer. Runs on CPU with no model downloads or API token required.

## Use the app

1. Upload documents in the sidebar and select **Process documents**, or select **Try a sample document**.
2. Ask a specific question in the chat input.
3. Open **View Source Chunks** under an answer to see the filename, page, and retrieved passages.
4. **Clear chat** keeps the current documents; **Reset documents** clears documents and conversation.
5. Download the conversation as a text file.

Source-excerpt mode is the default: it returns relevant passages, not generated answers. Optional **Use hosted AI** sends relevant passages and recent conversation to Hugging Face Inference Providers for an AI answer with numbered source references. Configure a server token or enter a personal token in the sidebar. Provider errors, missing credits, or unavailable models fall back to clearly labeled source excerpts.

## Run locally

Python 3.12 is the tested runtime.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Optional environment variables (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| HF_TOKEN | unset | Hosted inference credential; also supports Streamlit secrets |
| HF_MODEL | Qwen/Qwen2.5-7B-Instruct | Provider-served chat model |
| EMBEDDING_BACKEND | tfidf | CPU lexical search; optional sentence-transformers |
| EMBEDDING_MODEL | sentence-transformers/all-MiniLM-L6-v2 | Optional semantic model |

A token needs permission to call Inference Providers. Model availability and credits depend on the account/provider. The app never downloads a local generation model.

The default search uses a fitted TF-IDF vocabulary with normalized FAISS inner-product search. It is fast and offline, but synonyms and broad summaries can miss relevant passages. Optional semantic search requires `requirements-semantic.txt` and `EMBEDDING_BACKEND=sentence-transformers`; it uses more RAM and downloads MiniLM. The deployed default uses TF-IDF.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

Tests cover PDF extraction, empty/scanned/encrypted/corrupt files, text encoding, chunk overlap, FAISS retrieval, session isolation, index replacement, provider fallback, history, citations, and Streamlit chat/reset behavior. No GPU, API token, or network is required for the test suite. GitHub Actions runs the tests on Linux/Python 3.12.

`requirements.in` declares direct dependencies; `requirements.txt` pins the complete core environment. To refresh it with uv:

```bash
uv pip compile requirements.in --python-version 3.12 --output-file requirements.txt
```

## Deploy to Hugging Face Spaces

Create a **Docker Space** named `ai-document-chatbot` and upload this repository's tracked files. The README metadata sets `sdk: docker` and port `7860`; the Dockerfile runs Streamlit as a non-root user on that port. Use the free CPU tier when available; no GPU is required.

Optional: in **Settings → Variables and secrets**, add `HF_TOKEN` as a secret and `HF_MODEL` as a variable. Never put the token in source code, README, build arguments, or Git remotes. The application works without this secret in source-excerpt mode.

```bash
docker build -t ai-document-chatbot .
docker run --rm -p 7860:7860 ai-document-chatbot
```

After the build reports Running, open the public app, upload a small PDF, select Process documents, ask a question, and check its source citation. The health endpoint is `/_stcore/health`.

## Limits and privacy

- Up to 10 documents, 10 MB per document, 200 pages per PDF, one million extracted characters, and 2,000 chunks per batch.
- Scanned/image-only PDFs require OCR beforehand; encrypted PDFs must be unlocked.
- Documents and indexes stay in session memory. The app does not save uploads, chat, or indexes to shared files or global Streamlit caches. Closing/refreshing a session or restarting the Space may clear its state.
- Hosted AI is opt-in. It transmits relevant passages and the last few messages to Hugging Face and its selected provider. Source-excerpt mode makes no inference requests.
- This public demo has no account authentication or durable conversation storage. Do not upload confidential documents to a public demo. Generated answers can be wrong; verify source passages.
- Chat history is bounded to recent turns. Follow-ups use the prior question for retrieval and recent messages for hosted generation.

## Modules

- `app.py`: upload workflow, session state, chat, sources, and export.
- `document_processor/loader.py`: bounded PDF/TXT extraction and page-aware chunks.
- `embeddings/embedder.py`: fitted TF-IDF or optional CPU Sentence-Transformers.
- `retrieval/faiss_store.py`: in-memory per-session FAISS cosine search.
- `llm/generator.py`: hosted inference and explicit source-excerpt fallback.
- `utils/conversation.py`: short follow-up retrieval context.
