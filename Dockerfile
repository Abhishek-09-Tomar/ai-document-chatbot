# 1. Use Python 3.12 for maximum AI library compatibility

# here i change it to 3.13-slim to 3.10-slim(because pytorch did not support that)
FROM python:3.10-slim


# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory
WORKDIR /app

# 4. Install system dependencies for document processing & FAISS
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy all your project folders (embeddings, llm, retrieval, etc.)
COPY . .

# 7. Expose Streamlit's default port
EXPOSE 8501

# 8. Run the app
# Using 'streamlit run' as the entry point
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]