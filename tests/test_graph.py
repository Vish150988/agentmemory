"""Tests for memory graph visualization."""

from __future__ import annotations

from pathlib import Path

from agentmemory.core import MemoryEngine, MemoryEntry
from agentmemory.graph import build_memory_graph, get_category_clusters, get_timeline


def test_build_memory_graph_empty() -> None:
    db = Path("test_empty_graph.db")
    engine = MemoryEngine(db_path=db)
    data = build_memory_graph(engine, "empty", max_nodes=10)
    assert data["nodes"] == []
    assert data["edges"] == []
    db.unlink()


def test_build_memory_graph_with_memories(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(MemoryEntry(project="g", session_id="s", content="auth system with JWT"))
    engine.store(MemoryEntry(project="g", session_id="s", content="login page with OAuth"))
    engine.store(MemoryEntry(project="g", session_id="s", content="database schema users"))

    data = build_memory_graph(engine, "g", max_nodes=10)
    assert len(data["nodes"]) == 3
    # Edges may or may not exist depending on similarity threshold
    assert "edges" in data


def test_get_category_clusters(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(MemoryEntry(
        project="g", session_id="s", content="fact one", category="fact"
    ))
    engine.store(MemoryEntry(
        project="g", session_id="s", content="decision one", category="decision"
    ))

    clusters = get_category_clusters(engine, "g")
    assert "fact" in clusters
    assert "decision" in clusters
    assert len(clusters["fact"]) == 1


def test_get_timeline(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(MemoryEntry(project="g", session_id="s", content="event one"))

    timeline = get_timeline(engine, "g")
    assert len(timeline) == 1
    assert timeline[0]["content"] == "event one"
