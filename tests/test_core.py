"""Tests for the core memory engine."""

import tempfile
from pathlib import Path

from agentmemory.core import MemoryEngine, MemoryEntry


def test_init_creates_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        MemoryEngine(db_path=db_path)
        assert db_path.exists()


def test_store_and_recall():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        entry = MemoryEntry(
            project="test-proj",
            session_id="sess-1",
            category="decision",
            content="Chose PostgreSQL over MongoDB",
            confidence=0.95,
            source="user",
        )
        mid = engine.store(entry)
        assert mid > 0

        results = engine.recall(project="test-proj")
        assert len(results) == 1
        assert results[0].content == "Chose PostgreSQL over MongoDB"


def test_search():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(MemoryEntry(project="p", session_id="s", content="auth module with JWT"))
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="payment gateway integration",
            )
        )

        results = engine.search("auth")
        assert len(results) == 1
        assert "auth" in results[0].content


def test_project_context():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.set_project_context("my-app", {"stack": "Python,FastAPI"}, "My cool app")
        ctx = engine.get_project_context("my-app")
        assert ctx["stack"] == "Python,FastAPI"
