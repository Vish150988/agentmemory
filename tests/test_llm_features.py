"""Tests for LLM-powered features."""

from __future__ import annotations

from pathlib import Path

from crossagentmemory.core import MemoryEngine, MemoryEntry
from crossagentmemory.llm_features import (
    auto_tag_memory,
    detect_conflicts,
    generate_weekly_digest,
    summarize_project_llm,
)


def test_summarize_project_llm_fallback(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(MemoryEntry(project="p", session_id="s", content="test"))

    # Without API keys, should fall back to extractive summarizer
    text = summarize_project_llm(engine, "p")
    assert "test" in text or "No memories" in text


def test_weekly_digest_empty() -> None:
    db = Path("test_digest_empty.db")
    engine = MemoryEngine(db_path=db)
    text = generate_weekly_digest(engine, project="none")
    assert "No memories" in text or "none" in text.lower()
    db.unlink()


def test_auto_tag_memory_without_llm() -> None:
    tags = auto_tag_memory("some content")
    assert tags == []


def test_detect_conflicts_empty() -> None:
    db = Path("test_conflicts.db")
    engine = MemoryEngine(db_path=db)
    conflicts = detect_conflicts(engine, "empty")
    assert conflicts == []
    db.unlink()


def test_detect_conflicts_with_memories(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(
        MemoryEntry(project="p", session_id="s", content="Use PostgreSQL", category="decision")
    )
    engine.store(
        MemoryEntry(project="p", session_id="s", content="Use MongoDB", category="decision")
    )

    conflicts = detect_conflicts(engine, "p")
    assert isinstance(conflicts, list)
    db.unlink()
