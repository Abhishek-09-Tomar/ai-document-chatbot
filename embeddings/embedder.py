"""CPU-only fitted TF-IDF. No executable model code or serialized weights."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class EmbeddingEngine:
    def __init__(self, backend=None):
        self.backend = backend or 'tfidf'
        self.vectorizer = None
        if self.backend != 'tfidf':
            raise ValueError('Only the CPU tfidf backend is supported.')

    def fit_embed(self, texts):
        self.vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents='unicode', ngram_range=(1, 2),
            # token_pattern is a regex for words, not an authentication token.
            max_features=4096, token_pattern=r'(?u)\b\w+\b', sublinear_tf=True)  # nosec B106
        try:
            vectors = self.vectorizer.fit_transform(texts)
        except ValueError:
            raise ValueError('No searchable words were found in these documents.') from None
        return vectors.toarray().astype(np.float32)

    def embed(self, texts):
        if self.vectorizer is None:
            raise ValueError('Fit the document vocabulary before searching.')
        return self.vectorizer.transform(texts).toarray().astype(np.float32)
