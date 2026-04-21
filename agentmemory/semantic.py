"""Lightweight semantic search using TF-IDF + cosine similarity.

No heavy dependencies (no scikit-learn, no sentence-transformers).
Just numpy for vector math.
"""

from __future__ import annotations

import re

import numpy as np

from .core import MemoryEngine, MemoryEntry


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, filter short words."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", text)
    # Filter stop words and very short tokens
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "between", "under", "and", "but", "or", "yet", "so", "if",
        "because", "although", "though", "while", "where", "when",
        "that", "which", "who", "whom", "whose", "what", "this",
        "these", "those", "i", "you", "he", "she", "it", "we",
        "they", "me", "him", "her", "us", "them", "my", "your",
        "his", "its", "our", "their", "mine", "yours", "hers",
        "ours", "theirs", "am", "s", "t", "don", "didn", "wasn",
    }
    return [t for t in tokens if len(t) > 2 and t not in stop]


def _build_tfidf(documents: list[str]) -> tuple[np.ndarray, dict[str, int], list[int]]:
    """Build TF-IDF matrix from documents.

    Returns:
        - tfidf matrix: (n_docs, n_terms)
        - vocabulary: term -> index
        - doc_lengths: original token counts per doc
    """
    # Build vocabulary
    tokenized = [_tokenize(d) for d in documents]
    vocab: dict[str, int] = {}
    for tokens in tokenized:
        for t in tokens:
            if t not in vocab:
                vocab[t] = len(vocab)

    if not vocab:
        return np.zeros((len(documents), 1)), {"_empty_": 0}, [0] * len(documents)

    n_docs = len(documents)
    n_terms = len(vocab)

    # Term frequencies
    tf = np.zeros((n_docs, n_terms), dtype=np.float32)
    for i, tokens in enumerate(tokenized):
        for t in tokens:
            tf[i, vocab[t]] += 1

    # Document frequencies
    df = np.count_nonzero(tf, axis=0)
    # IDF with smoothing
    idf = np.log((n_docs + 1) / (df + 1)) + 1

    # TF-IDF
    tfidf = tf * idf

    # L2 normalize rows
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1  # avoid division by zero
    tfidf = tfidf / norms

    doc_lengths = [len(t) for t in tokenized]
    return tfidf, vocab, doc_lengths


def _query_vector(query: str, vocab: dict[str, int], n_docs: int) -> np.ndarray:
    """Convert query to TF-IDF vector using a simple approach."""
    tokens = _tokenize(query)
    n_terms = len(vocab)
    if n_terms == 0:
        return np.zeros((1, 1), dtype=np.float32)

    vec = np.zeros((1, n_terms), dtype=np.float32)
    for t in tokens:
        if t in vocab:
            vec[0, vocab[t]] += 1

    # Simple IDF weighting (assume uniform for query)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class SemanticIndex:
    """In-memory semantic index for a project's memories."""

    def __init__(self, engine: MemoryEngine, project: str):
        self.engine = engine
        self.project = project
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the index from all memories in the project."""
        self.memories = self.engine.recall(project=self.project, limit=10000)
        texts = [m.content for m in self.memories]
        if texts:
            self.tfidf, self.vocab, self.doc_lengths = _build_tfidf(texts)
        else:
            self.tfidf = np.zeros((0, 1), dtype=np.float32)
            self.vocab = {}
            self.doc_lengths = []

    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        """Find memories semantically related to query."""
        if len(self.memories) == 0:
            return []

        qvec = _query_vector(query, self.vocab, len(self.memories))
        # Cosine similarity = dot product of normalized vectors
        scores = (self.tfidf @ qvec.T).flatten()
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.memories[idx], float(scores[idx])))
        return results

    def find_related(self, memory_id: int, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        """Find memories related to a given memory by ID."""
        # Find the memory
        target = None
        target_idx = -1
        for i, m in enumerate(self.memories):
            if m.id == memory_id:
                target = m
                target_idx = i
                break

        if target is None or len(self.memories) == 0:
            return []

        # Use the target's vector as query
        target_vec = self.tfidf[target_idx:target_idx + 1].T
        scores = (self.tfidf @ target_vec).flatten()
        # Exclude self
        scores[target_idx] = -1

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.memories[idx], float(scores[idx])))
        return results
