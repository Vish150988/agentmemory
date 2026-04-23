"""Tests for semantic search backends."""

import tempfile
from pathlib import Path

from crossagentmemory.core import MemoryEngine, MemoryEntry
from crossagentmemory.semantic import SemanticIndex


def test_tfidf_backend():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="authentication system with JWT tokens",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="login page redesign with OAuth",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="database schema for users table",
            )
        )

        index = SemanticIndex(engine, "p", backend="tfidf")
        results = index.search("auth login", top_k=2)
        assert len(results) >= 1


def test_sentence_transformers_backend():
    """Test sentence-transformers backend if available."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        # Skip if sentence-transformers not installed
        return

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="FastAPI web framework for building APIs",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="Redis caching layer configuration",
            )
        )

        index = SemanticIndex(engine, "p", backend="sentence-transformers")
        results = index.search("python web framework", top_k=2)

        # Should find the FastAPI memory with decent similarity
        assert len(results) >= 1
        assert "FastAPI" in results[0][0].content
        assert results[0][1] > 0.1


def test_auto_backend_falls_back_to_tfidf():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)
        engine.store(MemoryEntry(project="p", session_id="s", content="test memory"))

        # "auto" should always work regardless of ST availability
        index = SemanticIndex(engine, "p", backend="auto")
        results = index.search("test")
        assert len(results) == 1


def test_backend_caches_embeddings():
    """Verify embeddings are stored in SQLite for ST backend."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        mid = engine.store(MemoryEntry(project="p", session_id="s", content="caching test"))

        index = SemanticIndex(engine, "p", backend="sentence-transformers")
        index.search("cache")

        # Embedding should now be cached
        cached = engine.get_embeddings("p", "all-MiniLM-L6-v2")
        ids = [i for i, _ in cached]
        assert mid in ids
