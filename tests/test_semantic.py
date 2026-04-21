"""Tests for semantic search."""

import tempfile
from pathlib import Path

from agentmemory.core import MemoryEngine, MemoryEntry
from agentmemory.semantic import SemanticIndex


def test_semantic_search_finds_related():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        # Store related memories
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

        index = SemanticIndex(engine, "p")
        results = index.search("auth login", top_k=2)

        assert len(results) >= 1
        # The JWT auth or login memory should rank highest
        assert "auth" in results[0][0].content.lower() or "login" in results[0][0].content.lower()


def test_semantic_search_empty_project():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)
        index = SemanticIndex(engine, "empty-project")
        results = index.search("anything")
        assert results == []


def test_find_related_memories():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(MemoryEntry(project="p", session_id="s", content="use Redis for caching"))
        mid = engine.store(MemoryEntry(project="p", session_id="s", content="Redis cache TTL bug"))
        engine.store(MemoryEntry(project="p", session_id="s", content="unrelated database topic"))

        index = SemanticIndex(engine, "p")
        related = index.find_related(mid, top_k=2)

        assert len(related) >= 1
        # The other Redis memory should be most related
        assert "redis" in related[0][0].content.lower()
