"""Tests for summarization."""

import tempfile
from pathlib import Path

from agentmemory.core import MemoryEngine, MemoryEntry
from agentmemory.summarize import summarize_project, summarize_session


def test_summarize_project():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(
            MemoryEntry(
                project="p",
                session_id="s1",
                category="decision",
                content="Chose FastAPI",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s1",
                category="error",
                content="Redis bug",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s1",
                category="preference",
                content="Use Pydantic",
            )
        )

        summary = summarize_project(engine, "p")
        assert "Chose FastAPI" in summary
        assert "Redis bug" in summary
        assert "Total memories:** 3" in summary


def test_summarize_empty_project():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)
        summary = summarize_project(engine, "empty")
        assert "No memories found" in summary


def test_summarize_session():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(
            MemoryEntry(
                project="p",
                session_id="sess-abc",
                category="decision",
                content="Chose Postgres",
            )
        )
        engine.store(
            MemoryEntry(
                project="p",
                session_id="sess-abc",
                category="fact",
                content="Postgres supports JSONB",
            )
        )

        summary = summarize_session(engine, "sess-abc", project="p")
        assert "Chose Postgres" in summary
        assert "Postgres supports JSONB" in summary
        assert "Total memories: 2" in summary
