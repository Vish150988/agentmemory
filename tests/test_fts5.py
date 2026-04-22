"""Tests for FTS5 full-text search."""

from __future__ import annotations

from pathlib import Path

from agentmemory import MemoryEngine, MemoryEntry


class TestFTS5:
    def test_fts5_search_finds_content(self, tmp_path: Path) -> None:
        db = tmp_path / "fts.db"
        engine = MemoryEngine(db_path=db, backend="sqlite")
        engine.store(MemoryEntry(project="p", content="SQLite is a great database"))
        engine.store(MemoryEntry(project="p", content="PostgreSQL is powerful"))
        engine.store(MemoryEntry(project="p", content="Python is fun"))

        results = engine.search("database", project="p")
        assert any("database" in m.content for m in results)

    def test_fts5_ranked_order(self, tmp_path: Path) -> None:
        db = tmp_path / "rank.db"
        engine = MemoryEngine(db_path=db, backend="sqlite")
        # Store multiple memories with overlapping keywords
        for i in range(5):
            engine.store(MemoryEntry(project="p", content=f"memory number {i} about search"))

        results = engine.search("search", project="p", limit=3)
        assert len(results) <= 3
        assert all("search" in m.content for m in results)

    def test_fts5_fallback_to_like(self, tmp_path: Path) -> None:
        # Even if FTS5 fails, LIKE fallback should still work
        db = tmp_path / "fallback.db"
        engine = MemoryEngine(db_path=db, backend="sqlite")
        engine.store(MemoryEntry(project="p", content="fallback test content"))

        results = engine.search("fallback", project="p")
        assert len(results) == 1
        assert results[0].content == "fallback test content"
