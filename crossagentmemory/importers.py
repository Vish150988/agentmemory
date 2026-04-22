"""Import memories from other tools (Mem0, markdown, JSON)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import MemoryEngine, MemoryEntry


def import_from_mem0(mem0_dir: Path, engine: MemoryEngine | None = None) -> dict[str, int]:
    """Import memories from a Mem0 export directory.

    Mem0 stores memories in SQLite or as JSON files.
    This function looks for common Mem0 export formats.
    """
    engine = engine or MemoryEngine()
    imported = 0
    skipped = 0

    # Mem0 JSON export format
    json_files = list(mem0_dir.glob("*.json"))
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if isinstance(data, list):
            for item in data:
                entry = _mem0_item_to_entry(item)
                if entry:
                    engine.store(entry)
                    imported += 1
                else:
                    skipped += 1
        elif isinstance(data, dict) and "memories" in data:
            for item in data["memories"]:
                entry = _mem0_item_to_entry(item)
                if entry:
                    engine.store(entry)
                    imported += 1
                else:
                    skipped += 1

    # Mem0 SQLite format
    sqlite_files = list(mem0_dir.glob("*.db"))
    for db in sqlite_files:
        try:
            import sqlite3

            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memories").fetchall()
            for row in rows:
                item = dict(row)
                entry = _mem0_item_to_entry(item)
                if entry:
                    engine.store(entry)
                    imported += 1
                else:
                    skipped += 1
            conn.close()
        except Exception:
            continue

    return {"imported": imported, "skipped": skipped}


def _mem0_item_to_entry(item: dict[str, Any]) -> MemoryEntry | None:
    """Convert a Mem0 memory item to CrossAgentMemory MemoryEntry."""
    content = item.get("memory") or item.get("content") or item.get("text")
    if not content:
        return None

    category_map = {
        "preference": "preference",
        "fact": "fact",
        "event": "action",
        "decision": "decision",
        "error": "error",
    }
    mem0_type = item.get("type", "fact")
    category = category_map.get(mem0_type, "fact")

    timestamp = item.get("created_at") or item.get("timestamp")
    if timestamp and isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    return MemoryEntry(
        project=item.get("user_id", item.get("agent_id", "imported")),
        session_id=item.get("session_id", "mem0-import"),
        category=category,
        content=str(content),
        confidence=item.get("score", 1.0),
        source="mem0-import",
        tags=",".join(item.get("categories", [])),
        timestamp=timestamp or "",
        metadata=json.dumps(
            {k: v for k, v in item.items() if k not in ("memory", "content", "text")}
        ),
    )


def import_from_markdown(md_path: Path, project: str, engine: MemoryEngine | None = None) -> int:
    """Import memories from a markdown file.

    Expects format:
    - **[decision]** Chose PostgreSQL
    - **[fact]** User table has 50M rows
    """
    engine = engine or MemoryEngine()
    text = md_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*[-*]\s*\[?(\w+)\]?\s*(.+)$", re.MULTILINE)

    count = 0
    for match in pattern.finditer(text):
        category = match.group(1).lower()
        content = match.group(2).strip()
        if category not in ("fact", "decision", "action", "preference", "error"):
            category = "fact"

        entry = MemoryEntry(
            project=project,
            session_id="markdown-import",
            category=category,
            content=content,
            confidence=0.8,
            source="markdown-import",
            tags="import,markdown",
        )
        engine.store(entry)
        count += 1

    return count


def import_from_json(json_path: Path, project: str, engine: MemoryEngine | None = None) -> int:
    """Import memories from a generic JSON file.

    Expects either a list of objects or an object with a 'memories' key.
    """
    engine = engine or MemoryEngine()
    data = json.loads(json_path.read_text(encoding="utf-8"))

    items: list[dict[str, Any]] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "memories" in data:
        items = data["memories"]

    count = 0
    for item in items:
        content = item.get("content") or item.get("memory") or item.get("text")
        if not content:
            continue

        entry = MemoryEntry(
            project=project,
            session_id=item.get("session_id", "json-import"),
            category=item.get("category", "fact"),
            content=str(content),
            confidence=item.get("confidence", 0.8),
            source=item.get("source", "json-import"),
            tags=item.get("tags", "import,json"),
            timestamp=item.get("timestamp", ""),
        )
        engine.store(entry)
        count += 1

    return count


def import_from_obsidian(
    vault_dir: Path,
    project: str | None = None,
    engine: MemoryEngine | None = None,
) -> int:
    """Import memories from an Obsidian vault directory.

    Parses Markdown files with YAML frontmatter. Each file becomes one memory entry.
    """
    engine = engine or MemoryEngine()
    count = 0
    for md_file in vault_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        frontmatter: dict[str, Any] = {}
        body = text

        # Parse YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml

                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except Exception:
                    pass

        if not body.strip():
            continue

        proj = project or frontmatter.get("project") or md_file.parent.name or "obsidian"
        tags = frontmatter.get("tags", [])
        if isinstance(tags, list):
            tags = ",".join(str(t) for t in tags)
        else:
            tags = str(tags)

        # Extract #hashtags from body as additional tags, and strip them from content
        hashtags = set(re.findall(r"#(\w+)", body))
        if hashtags:
            tags = ",".join(filter(None, [tags, ",".join(sorted(hashtags))]))
            body = re.sub(r"#\w+", "", body).strip()

        ts = frontmatter.get("date") or frontmatter.get("created")
        if not ts:
            ts = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc).isoformat()

        entry = MemoryEntry(
            project=proj,
            session_id="obsidian-import",
            category=frontmatter.get("category", "fact"),
            content=body[:2000],  # Truncate very long notes
            confidence=0.8,
            source="obsidian-import",
            tags=tags or "import,obsidian",
            timestamp=ts if isinstance(ts, str) else str(ts),
        )
        engine.store(entry)
        count += 1

    return count


def import_from_notion(
    notion_path: Path,
    project: str | None = None,
    engine: MemoryEngine | None = None,
) -> int:
    """Import memories from a Notion export (ZIP or folder).

    Parses Markdown files and CSV databases from the export.
    """
    engine = engine or MemoryEngine()
    import tempfile
    import zipfile

    extract_dir = notion_path
    cleanup_dir: Path | None = None

    if notion_path.suffix.lower() == ".zip":
        cleanup_dir = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(notion_path, "r") as zf:
            zf.extractall(cleanup_dir)
        extract_dir = cleanup_dir

    count = 0

    # Import Markdown files
    for md_file in extract_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        if not text.strip():
            continue
        proj = project or md_file.parent.name or "notion"
        entry = MemoryEntry(
            project=proj,
            session_id="notion-import",
            category="fact",
            content=text[:2000],
            confidence=0.8,
            source="notion-import",
            tags="import,notion",
        )
        engine.store(entry)
        count += 1

    # Import CSV databases
    for csv_file in extract_dir.rglob("*.csv"):
        try:
            import csv

            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    content = row.get("Name") or row.get("Title") or row.get("Content")
                    if not content:
                        continue
                    proj = project or csv_file.parent.name or "notion"
                    tags = [
                        k for k, v in row.items() if v and k not in ("Name", "Title", "Content")
                    ]
                    entry = MemoryEntry(
                        project=proj,
                        session_id="notion-import",
                        category="fact",
                        content=str(content)[:2000],
                        confidence=0.8,
                        source="notion-import",
                        tags=",".join(tags) if tags else "import,notion",
                    )
                    engine.store(entry)
                    count += 1
        except Exception:
            continue

    if cleanup_dir:
        import shutil

        shutil.rmtree(cleanup_dir, ignore_errors=True)

    return count
