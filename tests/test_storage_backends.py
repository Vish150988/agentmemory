"""Tests for pluggable storage backends."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentmemory.backends import SQLiteBackend
from agentmemory.backends.base import MemoryBackend
from agentmemory.core import MemoryEngine, MemoryEntry


def test_sqlite_backend_is_memory_backend() -> None:
    backend = SQLiteBackend()
    assert isinstance(backend, MemoryBackend)


def test_sqlite_backend_crud(tmp_path: Path) -> None:
    db = tmp_path / "backend.db"
    backend = SQLiteBackend(db_path=db)
    backend.init()

    entry = MemoryEntry(project="test", session_id="s1", content="hello", category="fact")
    memory_id = backend.store(entry)
    assert memory_id > 0

    memories = backend.recall(project="test")
    assert len(memories) == 1
    assert memories[0].content == "hello"

    retrieved = backend.get_memory_by_id(memory_id)
    assert retrieved is not None
    assert retrieved.content == "hello"

    backend.update_memory(memory_id, {"confidence": 0.5})
    updated = backend.get_memory_by_id(memory_id)
    assert updated.confidence == 0.5

    backend.delete_memory(memory_id)
    assert backend.get_memory_by_id(memory_id) is None


def test_memory_engine_uses_sqlite_by_default(tmp_path: Path) -> None:
    db = tmp_path / "engine.db"
    engine = MemoryEngine(db_path=db, backend="sqlite")
    engine.store(MemoryEntry(project="p", session_id="s", content="test"))
    assert len(engine.recall(project="p")) == 1


def test_memory_engine_list_projects(tmp_path: Path) -> None:
    db = tmp_path / "projects.db"
    engine = MemoryEngine(db_path=db, backend="sqlite")
    engine.store(MemoryEntry(project="alpha", session_id="s", content="a"))
    engine.store(MemoryEntry(project="beta", session_id="s", content="b"))
    projects = engine.list_projects()
    assert "alpha" in projects
    assert "beta" in projects


def test_postgres_backend_not_available_without_psycopg() -> None:
    try:
        from agentmemory.backends import PostgresBackend  # noqa: F401

        # If import succeeds, psycopg is installed — skip this test
        pytest.skip("psycopg is installed")
    except ImportError:
        pass


def test_postgres_backend_crud() -> None:
    """Test Postgres backend CRUD when DATABASE_URL is available."""
    import os
    import uuid

    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")

    from agentmemory.backends import PostgresBackend

    if PostgresBackend is None:
        pytest.skip("psycopg not installed")

    backend = PostgresBackend()
    backend.init()

    project = f"pgtest_{uuid.uuid4().hex[:8]}"
    try:
        entry = MemoryEntry(
            project=project,
            session_id="s1",
            content="postgres hello",
            category="fact",
        )
        memory_id = backend.store(entry)
        assert memory_id > 0

        memories = backend.recall(project=project)
        assert len(memories) == 1
        assert memories[0].content == "postgres hello"

        retrieved = backend.get_memory_by_id(memory_id)
        assert retrieved is not None
        assert retrieved.content == "postgres hello"

        backend.update_memory(memory_id, {"confidence": 0.5})
        updated = backend.get_memory_by_id(memory_id)
        assert updated.confidence == 0.5

        backend.delete_memory(memory_id)
        assert backend.get_memory_by_id(memory_id) is None
    finally:
        # Clean up project context if any
        backend.delete_project(project)
        backend.close()
