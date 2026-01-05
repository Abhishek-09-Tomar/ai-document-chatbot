import os
import faiss
import pickle
import numpy as np

class VectorStore:
    def __init__(self, embedder, index_path="faiss_index"):
        """
        embedder: an object with an embed_text(text:str)->np.array method
        index_path: path to save/load FAISS index
        """
        self.embedder = embedder
        self.index_path = index_path
        self.index = None
        self.docs = []

    def build_or_load(self, docs):
        """
        Build FAISS index from docs or load from disk if exists.
        """
        self.docs = docs
        if os.path.exists(self.index_path + ".index") and os.path.exists(self.index_path + ".pkl"):
            # Load index
            self.index = faiss.read_index(self.index_path + ".index")
            with open(self.index_path + ".pkl", "rb") as f:
                self.docs = pickle.load(f)
        else:
            # Build index
            embeddings = np.array([self.embedder.embed_text(d["text"]) for d in docs]).astype("float32")
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(embeddings)
            # Save to disk
            faiss.write_index(self.index, self.index_path + ".index")
            with open(self.index_path + ".pkl", "wb") as f:
                pickle.dump(docs, f)

    def search(self, query, top_k=5, rerank_top_k=5):
        """
        Search for top_k relevant documents given a query.
        """
        if self.index is None or len(self.docs) == 0:
            return []

        query_vec = np.array([self.embedder.embed_text(query)]).astype("float32")
        D, I = self.index.search(query_vec, top_k)
        results = [self.docs[i] for i in I[0] if i < len(self.docs)]
        return results[:rerank_top_k]
