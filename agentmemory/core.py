"""Core memory engine backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_MEMORY_DIR = Path.home() / ".agent-memory"
DEFAULT_DB_PATH = DEFAULT_MEMORY_DIR / "memory.db"


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: Optional[int] = None
    project: str = "default"
    session_id: str = ""
    timestamp: str = ""
    category: str = "fact"  # fact, decision, action, preference, error
    content: str = ""
    confidence: float = 1.0
    source: str = ""  # e.g., "claude-code", "codex", "user", "test"
    tags: str = ""  # comma-separated
    metadata: str = "{}"  # JSON blob for extensibility

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class MemoryEngine:
    """SQLite-backed memory engine."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        conn.close()

    def _init_db(self) -> None:
        conn = self._connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL DEFAULT 'default',
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'fact',
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '{}'  -- JSON: key files, conventions, stack
                )
                """
            )
            conn.commit()
        finally:
            self._close(conn)

    def store(self, entry: MemoryEntry) -> int:
        """Store a memory entry. Returns the inserted row ID."""
        conn = self._connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO memories (
                    project, session_id, timestamp, category,
                    content, confidence, source, tags, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.project,
                    entry.session_id,
                    entry.timestamp,
                    entry.category,
                    entry.content,
                    entry.confidence,
                    entry.source,
                    entry.tags,
                    entry.metadata,
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            self._close(conn)

    def recall(
        self,
        project: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        session_id: Optional[str] = None,
    ) -> list[MemoryEntry]:
        """Recall memories with optional filtering."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if project:
            query += " AND project = ?"
            params.append(project)
        if category:
            query += " AND category = ?"
            params.append(category)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self._connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [MemoryEntry(**dict(row)) for row in rows]
        finally:
            self._close(conn)

    def search(
        self,
        keyword: str,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Simple keyword search over memory content."""
        query = "SELECT * FROM memories WHERE content LIKE ?"
        params: list[Any] = [f"%{keyword}%"]

        if project:
            query += " AND project = ?"
            params.append(project)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self._connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [MemoryEntry(**dict(row)) for row in rows]
        finally:
            self._close(conn)

    def get_project_context(self, project: str) -> dict[str, Any]:
        """Get stored project context."""
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT context FROM projects WHERE name = ?", (project,)
            ).fetchone()
            if row:
                return json.loads(row["context"])
            return {}
        finally:
            self._close(conn)

    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
        """Set or update project context."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connection()
        try:
            conn.execute(
                """
                INSERT INTO projects (name, description, created_at, updated_at, context)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description=excluded.description,
                    updated_at=excluded.updated_at,
                    context=excluded.context
                """,
                (project, description, now, now, json.dumps(context)),
            )
            conn.commit()
        finally:
            self._close(conn)

    def stats(self) -> dict[str, Any]:
        """Return basic stats about the memory store."""
        conn = self._connection()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
            projects = conn.execute(
                "SELECT COUNT(DISTINCT project) as c FROM memories"
            ).fetchone()["c"]
            sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) as c FROM memories"
            ).fetchone()["c"]
            categories = conn.execute(
                "SELECT category, COUNT(*) as c FROM memories GROUP BY category"
            ).fetchall()
            return {
                "total_memories": total,
                "projects": projects,
                "sessions": sessions,
                "by_category": {row["category"]: row["c"] for row in categories},
            }
        finally:
            self._close(conn)

    def delete_project(self, project: str) -> int:
        """Delete all memories for a project. Returns number of rows deleted."""
        conn = self._connection()
        try:
            cursor = conn.execute("DELETE FROM memories WHERE project = ?", (project,))
            conn.execute("DELETE FROM projects WHERE name = ?", (project,))
            conn.commit()
            return cursor.rowcount
        finally:
            self._close(conn)
