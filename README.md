---
title: AI Document Chatbot
emoji: 📄
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# AI document chatbot

Upload PDFs or UTF-8 text files, ask follow-up questions, and inspect the source passages behind each answer. The default CPU search works offline without API credentials or model downloads.

## Use the app

1. Upload documents in the sidebar and select **Process documents**, or select **Try a sample document**.
2. Ask a specific question and open **View Source Chunks** to check the filename, page, and passages.
3. **Clear chat** keeps the documents; **Reset documents** clears the documents and conversation. Neither resets abuse-prevention counters.
4. Download the conversation as plain text.

Source-excerpt mode returns passages rather than generated answers. **Use hosted AI** is optional and sends relevant passages and recent conversation to Hugging Face Inference Providers. Public visitors must supply their own Hugging Face token. Provider errors or exhausted budgets fall back to source excerpts.

## Run locally

Python 3.12 is the tested runtime.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
streamlit run app.py
```

The app reads operator credentials only from the process environment or Streamlit secrets. It does not automatically load a .env file. Personal tokens use a password field and remain in session memory.

| Setting | Default | Purpose |
| --- | --- | --- |
| HF_TOKEN | unset | Optional server inference credential; inaccessible to anonymous users |
| HF_MODEL | Qwen/Qwen2.5-7B-Instruct | Hugging Face chat model ID; URL endpoints are rejected |

A server token is eligible only when Streamlit reports a trusted signed-in user. Authentication is not configured by this demo; configuring an OIDC provider and the required Streamlit auth dependencies is a separate operator task. Personal tokens work without that setup. Inference requires provider permission and possibly account credits.

Search uses a fitted TF-IDF vocabulary and normalized FAISS inner products. It can miss synonyms and broad questions; ask specific questions using document terms. The previous optional PyTorch/Sentence-Transformers stack was removed during security hardening. No serialized model weights or executable remote model code are loaded.

## Limits

- Five files per batch, 10 MB each, 25 MB combined.
- 100 pages per PDF, 500,000 extracted characters and 1,000 chunks per batch.
- PDF worker: 20-second wall timeout; on Linux, 384 MiB address space and 12-second CPU limit. Decoder and page-tree limits also apply.
- Two concurrent processing operations and eight active document indexes per process.
- Twenty questions and ten processing attempts per session, with two-second cooldowns.
- Hosted inference: four source chunks, bounded XML prompt data, six recent history messages, and at most 512 output tokens.
- Per-token hosted budget: twenty attempts per hour and a two-second cooldown across sessions. Shared server credentials additionally have a forty-attempt lifetime budget per process. At most two hosted requests run concurrently.
- Scanned/image-only PDFs need OCR beforehand. Encrypted PDFs must be unlocked. Strict parsing may reject damaged PDFs that other readers repair.

## Tests and security checks

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python -m pytest -q
python -m pip check
bandit -r app.py document_processor embeddings retrieval llm utils scripts
pip-audit -r requirements.txt --no-deps --disable-pip
python scripts/scan_secrets.py
```

The tests cover normal document Q&A, corrupt/scanned/encrypted PDFs, disguised binary uploads, decompression limits, parser isolation/timeouts, prompt boundaries, quotas, secret-safe diagnostics, citations, and session isolation. The OS address-space test runs on Linux and skips on Windows.

GitHub Actions pins its actions to verified commits, grants read-only repository permission, installs hash-locked dependencies, and runs tests, Bandit, dependency auditing, and a redacted history secret scan.

To refresh locks with uv, audit and test the changes before committing them:

```bash
uv pip compile requirements.in --upgrade --python-version 3.12 --universal --generate-hashes --output-file requirements.txt
uv pip compile requirements-dev.in --python-version 3.12 --universal --generate-hashes --output-file requirements-dev.txt
```

## Deploy to Hugging Face Spaces

Use a **Docker Space**. The Dockerfile runs as UID/GID 1000 with root-owned application code, listens on port 7860, explicitly enables CORS/XSRF protection, and disables the development agent API. The README metadata declares the SDK and port.

The host allowlist contains localhost, 127.0.0.1, and `abhishek-tomar-1-ai-document-chatbot.hf.space`. Update it deliberately when deploying to another domain. Use the direct .hf.space URL for the app; do not disable XSRF protection to work around iframe/browser cookie restrictions.

```bash
docker build -t ai-document-chatbot .
docker run --rm -p 7860:7860 ai-document-chatbot
```

Do not upload .env files, Streamlit secret files, private keys, virtual environments, or caches. The app works without a server secret; public hosted generation uses each visitor's personal token.

After deployment, check Running status and `/_stcore/health`, upload a small PDF, ask a question, and inspect its sources. The deployment helper used during development is outside this repository and never embeds a credential in a Git remote.

## Security and privacy

Documents, indexes, keys, and chat are held in session memory. The app does not write uploads or indexes to shared files. The PDF worker receives bytes over stdin, returns JSON, and does not inherit credentials from the server environment. No pickle/eval/exec, shell commands from input, or unsafe dynamic HTML are used.

Prompt delimiters and control-token filtering reduce injection risk; they cannot guarantee factual or obedient model output. Responses and document snippets render as literal text and cannot execute links, images, HTML, or scripts through the app.

Application limits are per process and are not a distributed firewall or a financial guarantee. Session quotas can be evaded by new sessions; reverse-proxy limits, container memory/CPU ceilings, authentication where needed, and provider-side spending caps remain operator responsibilities. Windows local development enforces worker timeouts but not Linux OS memory/CPU limits.

See [SECURITY.md](SECURITY.md) for findings, remediation, and remaining boundaries. Verify source passages before relying on an answer.
