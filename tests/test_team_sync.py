"""Tests for team sync functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentmemory.core import MemoryEngine, MemoryEntry
from agentmemory.team_sync import team_export, team_import, team_status


@pytest.fixture
def temp_engine(tmp_path: Path) -> MemoryEngine:
    db = tmp_path / "test.db"
    return MemoryEngine(db_path=db)


def test_team_export_creates_json(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    engine = temp_engine
    engine.store(MemoryEntry(project="demo", content="Team decision", category="decision"))
    engine.store(MemoryEntry(project="demo", content="Team fact", category="fact"))

    export_path = team_export("demo", cwd=tmp_path, engine=engine)
    assert export_path.exists()
    assert export_path.parent.name == ".agent-memory"
    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert data["project"] == "demo"
    assert len(data["memories"]) == 2
    assert data["version"] == "1.0"


def test_team_import_skips_duplicates(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    engine = temp_engine
    engine.store(MemoryEntry(project="demo", content="Team decision", category="decision"))

    # Export then import should skip duplicate
    team_export("demo", cwd=tmp_path, engine=engine)
    stats = team_import("demo", cwd=tmp_path, engine=engine)
    assert stats["imported"] == 0
    assert stats["skipped"] == 1


def test_team_import_adds_new_memories(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    engine = temp_engine
    engine.store(MemoryEntry(project="demo", content="Original", category="fact"))

    # Export, add new local memory, then import back
    team_export("demo", cwd=tmp_path, engine=engine)
    engine.store(MemoryEntry(project="demo", content="New memory", category="action"))
    team_export("demo", cwd=tmp_path, engine=engine)

    # Start fresh engine and import
    fresh = MemoryEngine(db_path=tmp_path / "fresh.db")
    stats = team_import("demo", cwd=tmp_path, engine=fresh)
    # Both memories should be present; skipped may be >0 if multiple export
    # files contain overlapping content (different timestamps)
    assert stats["imported"] >= 2
    memories = fresh.recall(project="demo")
    assert any(m.content == "Original" for m in memories)
    assert any(m.content == "New memory" for m in memories)


def test_team_import_dry_run(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    engine = temp_engine
    engine.store(MemoryEntry(project="demo", content="Only", category="fact"))
    team_export("demo", cwd=tmp_path, engine=engine)

    fresh = MemoryEngine(db_path=tmp_path / "fresh.db")
    stats = team_import("demo", cwd=tmp_path, engine=fresh, dry_run=True)
    assert stats["imported"] == 1
    assert len(fresh.recall(project="demo")) == 0  # Not actually stored


def test_team_status(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    engine = temp_engine
    engine.store(MemoryEntry(project="demo", content="One", category="fact"))
    team_export("demo", cwd=tmp_path, engine=engine)

    info = team_status("demo", cwd=tmp_path, engine=engine)
    assert info["project"] == "demo"
    assert info["local_memories"] == 1
    assert info["team_folder_exists"] is True
    assert info["export_files"] == 1
    assert info["latest_export"] is not None


def test_team_status_no_folder(temp_engine: MemoryEngine, tmp_path: Path) -> None:
    info = team_status("missing", cwd=tmp_path)
    assert info["team_folder_exists"] is False
    assert info["export_files"] == 0
