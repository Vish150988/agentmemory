"""Tests for Obsidian and Notion importers."""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from crossagentmemory import MemoryEngine
from crossagentmemory.backends.sqlite import SQLiteBackend
from crossagentmemory.importers import import_from_notion, import_from_obsidian


def _make_engine(tmp_path: Path) -> MemoryEngine:
    db = tmp_path / "test.db"
    backend = SQLiteBackend(db_path=db)
    backend.init()
    engine = MemoryEngine.__new__(MemoryEngine)
    engine.backend = backend
    return engine


def test_import_from_obsidian(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note1.md").write_text(
        "---\n"
        "tags: [ai, memory]\n"
        "category: decision\n"
        "date: 2024-01-15\n"
        "---\n\n"
        "Chose vector DB for semantic search.\n\n"
        "#ml #embedding",
        encoding="utf-8",
    )
    (vault / "folder").mkdir()
    (vault / "folder" / "note2.md").write_text(
        "Just a plain note without frontmatter.\n\n#plain",
        encoding="utf-8",
    )

    engine = _make_engine(tmp_path)
    count = import_from_obsidian(vault, project="myproj", engine=engine)
    assert count == 2

    results = engine.backend.recall(project="myproj")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert "Chose vector DB for semantic search." in contents

    # Check tags merged from frontmatter and hashtags
    for r in results:
        if "vector DB" in r.content:
            assert "ai" in r.tags
            assert "memory" in r.tags
            assert "ml" in r.tags
            assert "embedding" in r.tags


def test_import_from_notion_folder(tmp_path: Path):
    notion_dir = tmp_path / "notion"
    notion_dir.mkdir()
    (notion_dir / "page1.md").write_text("Meeting notes about architecture.", encoding="utf-8")

    # CSV database
    with (notion_dir / "tasks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Name", "Status", "Priority"])
        writer.writeheader()
        writer.writerow({"Name": "Fix login bug", "Status": "Done", "Priority": "High"})
        writer.writerow({"Name": "Add tests", "Status": "In Progress", "Priority": "Medium"})

    engine = _make_engine(tmp_path)
    count = import_from_notion(notion_dir, project="work", engine=engine)
    assert count == 3

    results = engine.backend.recall(project="work")
    assert len(results) == 3


def test_import_from_notion_zip(tmp_path: Path):
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("page1.md", "Weekly review notes.")

    engine = _make_engine(tmp_path)
    count = import_from_notion(zip_path, project="reviews", engine=engine)
    assert count == 1

    results = engine.backend.recall(project="reviews")
    assert len(results) == 1
    assert results[0].content == "Weekly review notes."
