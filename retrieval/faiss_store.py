"""Per-session FAISS cosine search. No shared files, pickle, or document cache."""
import faiss
import numpy as np
import threading
import weakref
from document_processor.limits import MAX_CHUNKS
from utils.security import MAX_SOURCES, BudgetError, processing_slot

_LIVE_INDEXES = weakref.WeakSet()
_INDEX_LOCK = threading.Lock()
MAX_ACTIVE_INDEXES = 8

faiss.omp_set_num_threads(2)


class VectorStore:
    def __init__(self, embedder):
        self.embedder = embedder
        self.index = None
        self.docs = []

    def build_or_load(self, docs):
        # Compatible entry point; always builds from this session's documents.
        if not docs or len(docs) > MAX_CHUNKS:
            raise ValueError('Upload readable documents before building an index.')
        with _INDEX_LOCK:
            if self not in _LIVE_INDEXES and len(_LIVE_INDEXES) >= MAX_ACTIVE_INDEXES:
                raise BudgetError('The server has reached its active document limit. Please try again later.')
            _LIVE_INDEXES.add(self)
        try:
            with processing_slot():
                vectors = np.ascontiguousarray(self.embedder.fit_embed([d['text'] for d in docs]), dtype='float32')
                if vectors.ndim != 2 or vectors.shape[1] > 4096 or not np.isfinite(vectors).all():
                    raise ValueError('Invalid document embeddings.')
                faiss.normalize_L2(vectors)
                index = faiss.IndexFlatIP(vectors.shape[1])
                index.add(vectors)
                self.docs, self.index = list(docs), index
        except Exception:
            if self.index is None:
                with _INDEX_LOCK:
                    _LIVE_INDEXES.discard(self)
            raise

    def search(self, query, top_k=4, rerank_top_k=None, min_score=0.01):
        query = query[:2500]
        top_k = min(MAX_SOURCES, max(0, top_k))
        if self.index is None or not query.strip() or top_k <= 0:
            return []
        query_vector = np.ascontiguousarray(self.embedder.embed([query]), dtype='float32')
        faiss.normalize_L2(query_vector)
        scores, indices = self.index.search(query_vector, min(top_k, len(self.docs)))
        results = [dict(self.docs[int(i)], score=float(score))
                   for score, i in zip(scores[0], indices[0])
                   if 0 <= i < len(self.docs) and score >= min_score]
        return results if rerank_top_k is None else results[:rerank_top_k]
