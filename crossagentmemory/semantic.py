"""Lightweight semantic search with pluggable backends.

Backends:
- tfidf: Pure numpy TF-IDF + cosine similarity (default, no extra deps)
- sentence-transformers: Dense embeddings via sentence-transformers
  (install with: pip install crossagentmemory[embeddings])
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from .core import MemoryEngine, MemoryEntry


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, filter short words."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", text)
    stop = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "and",
        "but",
        "or",
        "yet",
        "so",
        "if",
        "because",
        "although",
        "though",
        "while",
        "where",
        "when",
        "that",
        "which",
        "who",
        "whom",
        "whose",
        "what",
        "this",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "mine",
        "yours",
        "hers",
        "ours",
        "theirs",
        "am",
        "s",
        "t",
        "don",
        "didn",
        "wasn",
    }
    return [t for t in tokens if len(t) > 2 and t not in stop]


# ---------------------------------------------------------------------------
# Base backend
# ---------------------------------------------------------------------------


class SemanticBackend(ABC):
    """Abstract base for semantic search backends."""

    def __init__(self, engine: MemoryEngine, project: str):
        self.engine = engine
        self.project = project

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        """Find memories semantically related to query."""
        ...

    @abstractmethod
    def find_related(self, memory_id: int, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        """Find memories related to a given memory by ID."""
        ...


# ---------------------------------------------------------------------------
# TF-IDF backend (default, no extra deps)
# ---------------------------------------------------------------------------


class _TFIDFBackend(SemanticBackend):
    """TF-IDF + cosine similarity using numpy."""

    def __init__(self, engine: MemoryEngine, project: str):
        super().__init__(engine, project)
        self._rebuild()

    def _build_tfidf(self, documents: list[str]) -> tuple[np.ndarray, dict[str, int], list[int]]:
        tokenized = [_tokenize(d) for d in documents]
        vocab: dict[str, int] = {}
        for tokens in tokenized:
            for t in tokens:
                if t not in vocab:
                    vocab[t] = len(vocab)

        if not vocab:
            return (
                np.zeros((len(documents), 1), dtype=np.float32),
                {"_empty_": 0},
                [0] * len(documents),
            )

        n_docs = len(documents)
        n_terms = len(vocab)

        tf = np.zeros((n_docs, n_terms), dtype=np.float32)
        for i, tokens in enumerate(tokenized):
            for t in tokens:
                tf[i, vocab[t]] += 1

        df = np.count_nonzero(tf, axis=0)
        idf = np.log((n_docs + 1) / (df + 1)) + 1
        tfidf = tf * idf

        norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
        norms[norms == 0] = 1
        tfidf = tfidf / norms

        doc_lengths = [len(t) for t in tokenized]
        return tfidf, vocab, doc_lengths

    def _query_vector(self, query: str, vocab: dict[str, int], n_docs: int) -> np.ndarray:
        tokens = _tokenize(query)
        n_terms = len(vocab)
        if n_terms == 0:
            return np.zeros((1, 1), dtype=np.float32)

        vec = np.zeros((1, n_terms), dtype=np.float32)
        for t in tokens:
            if t in vocab:
                vec[0, vocab[t]] += 1

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def _rebuild(self) -> None:
        self.memories = self.engine.recall(project=self.project, limit=10000)
        texts = [m.content for m in self.memories]
        if texts:
            self.tfidf, self.vocab, self.doc_lengths = self._build_tfidf(texts)
        else:
            self.tfidf = np.zeros((0, 1), dtype=np.float32)
            self.vocab = {}
            self.doc_lengths = []

    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        if len(self.memories) == 0:
            return []

        qvec = self._query_vector(query, self.vocab, len(self.memories))
        scores = (self.tfidf @ qvec.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.memories[idx], float(scores[idx])))
        return results

    def find_related(self, memory_id: int, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        target_idx = -1
        for i, m in enumerate(self.memories):
            if m.id == memory_id:
                target_idx = i
                break

        if target_idx == -1 or len(self.memories) == 0:
            return []

        target_vec = self.tfidf[target_idx : target_idx + 1].T
        scores = (self.tfidf @ target_vec).flatten()
        scores[target_idx] = -1

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.memories[idx], float(scores[idx])))
        return results


# ---------------------------------------------------------------------------
# Sentence-Transformers backend (optional)
# ---------------------------------------------------------------------------


class _STBackend(SemanticBackend):
    """Dense embeddings via sentence-transformers."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, engine: MemoryEngine, project: str):
        super().__init__(engine, project)
        from sentence_transformers import SentenceTransformer

        self.model_name = self.DEFAULT_MODEL
        self.model = SentenceTransformer(self.model_name)
        self._ensure_embeddings()

    def _ensure_embeddings(self) -> None:
        """Compute and cache embeddings for any memories that don't have them."""
        memories = self.engine.recall(project=self.project, limit=10000)
        cached = {mid for mid, _ in self.engine.get_embeddings(self.project, self.model_name)}

        to_encode = []
        to_encode_ids = []
        for m in memories:
            if m.id not in cached:
                to_encode.append(m.content)
                to_encode_ids.append(m.id)

        if to_encode:
            vectors = self.model.encode(to_encode, show_progress_bar=False)
            for mid, vec in zip(to_encode_ids, vectors):
                self.engine.store_embedding(mid, self.model_name, vec.tolist())

        self.memories = memories

    def _get_vectors(self) -> tuple[list[int], np.ndarray]:
        """Return (memory_ids, vectors_matrix) for all cached embeddings."""
        rows = self.engine.get_embeddings(self.project, self.model_name)
        if not rows:
            return [], np.zeros((0, 1), dtype=np.float32)

        ids = [mid for mid, _ in rows]
        vectors = np.array([vec for _, vec in rows], dtype=np.float32)
        return ids, vectors

    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        ids, vectors = self._get_vectors()
        if len(ids) == 0:
            return []

        qvec = self.model.encode([query], show_progress_bar=False)
        qvec = np.array(qvec, dtype=np.float32)

        # Cosine similarity = dot product of normalized vectors
        v_norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        v_norms[v_norms == 0] = 1
        vectors = vectors / v_norms

        q_norm = np.linalg.norm(qvec)
        if q_norm > 0:
            qvec = qvec / q_norm

        scores = (vectors @ qvec.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        id_to_memory = {m.id: m for m in self.memories}
        results = []
        for idx in top_indices:
            mid = ids[idx]
            if mid in id_to_memory and scores[idx] > 0:
                results.append((id_to_memory[mid], float(scores[idx])))
        return results

    def find_related(self, memory_id: int, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        ids, vectors = self._get_vectors()
        if len(ids) == 0:
            return []

        try:
            target_idx = ids.index(memory_id)
        except ValueError:
            return []

        target_vec = vectors[target_idx : target_idx + 1].T
        scores = (vectors @ target_vec).flatten()
        scores[target_idx] = -1

        top_indices = np.argsort(scores)[::-1][:top_k]
        id_to_memory = {m.id: m for m in self.memories}
        results = []
        for idx in top_indices:
            mid = ids[idx]
            if mid in id_to_memory and scores[idx] > 0:
                results.append((id_to_memory[mid], float(scores[idx])))
        return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SemanticIndex:
    """Semantic index that auto-selects the best available backend."""

    def __init__(
        self,
        engine: MemoryEngine,
        project: str,
        backend: Optional[str] = None,
    ):
        self.engine = engine
        self.project = project
        self._backend = self._resolve_backend(backend)

    def _resolve_backend(self, name: Optional[str]) -> SemanticBackend:
        """Resolve backend name to instance."""
        if name == "tfidf":
            return _TFIDFBackend(self.engine, self.project)

        if name == "sentence-transformers":
            try:
                return _STBackend(self.engine, self.project)
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Run: pip install crossagentmemory[embeddings]"
                ) from exc

        # Auto: prefer ST if available, else TF-IDF
        if name is None or name == "auto":
            try:
                return _STBackend(self.engine, self.project)
            except ImportError:
                return _TFIDFBackend(self.engine, self.project)

        raise ValueError(f"Unknown backend: {name}")

    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        return self._backend.search(query, top_k)

    def find_related(self, memory_id: int, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        return self._backend.find_related(memory_id, top_k)
