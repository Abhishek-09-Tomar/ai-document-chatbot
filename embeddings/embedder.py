import torch
import os
from sentence_transformers import SentenceTransformer

class EmbeddingEngine:
    def __init__(self):
        model_name = os.getenv("EMBEDDING_MODEL")
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self.device = device if torch.cuda.is_available() and device=="cuda" else "cpu"
        self.model = SentenceTransformer(model_name, device=self.device)

    def embed(self, texts):
        return self.model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            show_progress_bar=True
        )
