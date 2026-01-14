import os
import faiss
import pickle
import numpy as np


class VectorStore:
    def __init__(self, embedder, index_path="faiss_index"):
        """
        embedder: EmbeddingEngine instance
        index_path: base path to save/load FAISS index
        """
        self.embedder = embedder
        self.index_path = index_path
        self.index = None
        self.docs = []

    def _embed_text(self, text: str) -> np.ndarray:
        """
        Internal helper to generate embedding for a single text.
        Uses EmbeddingEngine.embed() safely.
        """
        embedding = self.embedder.embed([text])
        return embedding[0].astype("float32")

    def build_or_load(self, docs):
        """
        Build FAISS index from docs or load from disk if it exists.
        """
        self.docs = docs

        index_file = self.index_path + ".index"
        meta_file = self.index_path + ".pkl"

        # Load existing index if present
        if os.path.exists(index_file) and os.path.exists(meta_file):
            self.index = faiss.read_index(index_file)
            with open(meta_file, "rb") as f:
                self.docs = pickle.load(f)
            return

        # Build new index
        if not docs:
            raise ValueError("No documents provided to build FAISS index.")

        embeddings = np.array(
            [self._embed_text(d["text"]) for d in docs],
            dtype="float32"
        )

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

        # Persist index + metadata
        faiss.write_index(self.index, index_file)
        with open(meta_file, "wb") as f:
            pickle.dump(docs, f)

    def search(self, query: str, top_k=5, rerank_top_k=5):
        """
        Search FAISS index for relevant documents.
        """
        if self.index is None or not self.docs:
            return []

        query_vec = np.array(
            [self._embed_text(query)],
            dtype="float32"
        )

        distances, indices = self.index.search(query_vec, top_k)

        results = [
            self.docs[i]
            for i in indices[0]
            if 0 <= i < len(self.docs)
        ]

        return results[:rerank_top_k]
