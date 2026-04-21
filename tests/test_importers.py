"""Tests for importers."""

from __future__ import annotations

import json
from pathlib import Path

from agentmemory.core import MemoryEngine
from agentmemory.importers import import_from_json, import_from_markdown


def test_import_from_markdown(tmp_path: Path) -> None:
    md = tmp_path / "notes.md"
    md.write_text(
        "# Notes\n\n"
        "- [decision] Chose PostgreSQL\n"
        "- [fact] User table has 50M rows\n"
        "- [action] Added OAuth flow\n",
        encoding="utf-8",
    )
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    count = import_from_markdown(md, "demo", engine=engine)
    assert count == 3

    memories = engine.recall(project="demo")
    assert any(m.content == "Chose PostgreSQL" for m in memories)
    assert any(m.category == "fact" for m in memories)


def test_import_from_json(tmp_path: Path) -> None:
    data = [
        {"content": "Memory one", "category": "decision"},
        {"content": "Memory two", "category": "fact", "confidence": 0.9},
    ]
    jf = tmp_path / "memories.json"
    jf.write_text(json.dumps(data), encoding="utf-8")

    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    count = import_from_json(jf, "demo", engine=engine)
    assert count == 2

    memories = engine.recall(project="demo")
    assert len(memories) == 2
