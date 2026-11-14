"""CPU embeddings: fitted TF-IDF by default, optional Sentence-Transformers."""
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class EmbeddingEngine:
    def __init__(self, backend=None):
        self.backend = backend or os.getenv('EMBEDDING_BACKEND', 'tfidf')
        self.vectorizer = None
        self.model = None
        if self.backend == 'sentence-transformers':
            from sentence_transformers import SentenceTransformer  # ty: ignore[import-not-found] -- optional extra
            self.model = SentenceTransformer(
                os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'), device='cpu')
        elif self.backend != 'tfidf':
            raise ValueError('EMBEDDING_BACKEND must be tfidf or sentence-transformers.')

    def fit_embed(self, texts):
        if self.model is not None:
            return self.embed(texts)
        self.vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents='unicode', ngram_range=(1, 2),
            max_features=4096, token_pattern=r'(?u)\b\w+\b', sublinear_tf=True)
        try:
            vectors = self.vectorizer.fit_transform(texts)
        except ValueError:
            raise ValueError('No searchable words were found in these documents.') from None
        return vectors.toarray().astype(np.float32)

    def embed(self, texts):
        if self.model is not None:
            return self.model.encode(texts, batch_size=16, convert_to_numpy=True,
                                     normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
        if self.vectorizer is None:
            raise ValueError('Fit the document vocabulary before searching.')
        return self.vectorizer.transform(texts).toarray().astype(np.float32)
