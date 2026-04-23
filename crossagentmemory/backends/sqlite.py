"""SQLite storage backend for CrossAgentMemory."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core import DEFAULT_DB_PATH, MemoryEntry
from .base import MemoryBackend


class SQLiteBackend(MemoryBackend):
    """SQLite-backed memory storage."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        conn.close()

    def close(self) -> None:
        """No-op for API compatibility; SQLite connections are per-query."""
        pass

    def init(self) -> None:
        conn = self._connection()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
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
                    metadata TEXT NOT NULL DEFAULT '{}',
                    user_id TEXT NOT NULL DEFAULT '',
                    tenant_id TEXT NOT NULL DEFAULT '',
                    valid_from TEXT NOT NULL DEFAULT '',
                    valid_until TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            # New indexes may fail on pre-v2 databases until migrations run;
            # swallow errors so migration can add the columns first.
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_memories_tenant ON memories(tenant_id)",
                "CREATE INDEX IF NOT EXISTS idx_memories_valid_from ON memories(valid_from)",
                "CREATE INDEX IF NOT EXISTS idx_memories_valid_until ON memories(valid_until)",
            ):
                try:
                    conn.execute(idx_sql)
                except sqlite3.OperationalError:
                    pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    memory_id INTEGER PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_name)"
            )
            self._init_fts5(conn)
            conn.commit()
        finally:
            conn.close()

        from .migrations import run_migrations

        run_migrations(self)

    def _init_fts5(self, conn: sqlite3.Connection) -> None:
        """Initialize FTS5 virtual table for full-text search."""
        try:
            # Clean up any legacy triggers from older versions
            for trigger in ("memories_fts_insert", "memories_fts_delete", "memories_fts_update"):
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, content_rowid=rowid
                )
                """
            )
            # Backfill existing data if table is empty
            count = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
            if count == 0:
                conn.execute(
                    """
                    INSERT INTO memories_fts(rowid, content)
                    SELECT rowid, content FROM memories
                    """
                )
        except Exception:
            # FTS5 may not be available in all builds
            pass

    def _fts5_insert(self, conn: sqlite3.Connection, rowid: int, content: str) -> None:
        try:
            conn.execute(
                "INSERT INTO memories_fts(rowid, content) VALUES (?, ?)",
                (rowid, content),
            )
        except Exception:
            pass

    def _fts5_delete(self, conn: sqlite3.Connection, rowid: int) -> None:
        try:
            conn.execute(
                "INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', ?, '')",
                (rowid,),
            )
        except Exception:
            pass

    def _at_time_clause(self, params: list[Any], at_time: str | None) -> str:
        """Generate SQL clause for temporal validity at a specific time."""
        if not at_time:
            return ""
        params.extend([at_time, at_time])
        return (
            " AND (valid_from = '' OR valid_from <= ?) AND (valid_until = '' OR valid_until >= ?)"
        )

    def _user_tenant_clause(
        self, params: list[Any], user_id: str | None, tenant_id: str | None
    ) -> str:
        clause = ""
        if user_id is not None:
            clause += " AND user_id = ?"
            params.append(user_id)
        if tenant_id is not None:
            clause += " AND tenant_id = ?"
            params.append(tenant_id)
        return clause

    def store(self, entry: MemoryEntry) -> int:
        conn = self._connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO memories (
                    project, session_id, timestamp, category,
                    content, confidence, source, tags, metadata,
                    user_id, tenant_id, valid_from, valid_until
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    entry.user_id,
                    entry.tenant_id,
                    entry.valid_from,
                    entry.valid_until,
                ),
            )
            rowid = cursor.lastrowid
            if rowid:
                self._fts5_insert(conn, rowid, entry.content)
            conn.commit()
            return rowid  # type: ignore[return-value]
        finally:
            self._close(conn)

    def recall(
        self,
        project: str | None = None,
        category: str | None = None,
        limit: int = 50,
        session_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
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

        query += self._user_tenant_clause(params, user_id, tenant_id)
        query += self._at_time_clause(params, at_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self._connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [MemoryEntry(**dict(row)) for row in rows]
        finally:
            self._close(conn)

    def recall_temporal(
        self,
        project: str | None = None,
        at_time: str | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Recall memories overlapping a temporal window.

        If at_time is given, returns memories valid at that instant.
        If window_start and/or window_end are given, returns memories whose
        validity interval overlaps the window.
        """
        if at_time:
            return self.recall(project=project, at_time=at_time, limit=limit)

        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if project:
            query += " AND project = ?"
            params.append(project)

        if window_start:
            # Memory is valid if it hasn't expired before window_start
            query += " AND (valid_until = '' OR valid_until >= ?)"
            params.append(window_start)
        if window_end:
            # Memory is valid if it started before window_end
            query += " AND (valid_from = '' OR valid_from <= ?)"
            params.append(window_end)

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
        project: str | None = None,
        limit: int = 20,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
        conn = self._connection()
        try:
            # Try FTS5 first for ranked full-text search
            try:
                base_params: list[Any] = [keyword]
                where_parts = ["memories_fts MATCH ?"]
                if project:
                    where_parts.append("m.project = ?")
                    base_params.append(project)
                if user_id is not None:
                    where_parts.append("m.user_id = ?")
                    base_params.append(user_id)
                if tenant_id is not None:
                    where_parts.append("m.tenant_id = ?")
                    base_params.append(tenant_id)
                if at_time:
                    where_parts.append("(m.valid_from = '' OR m.valid_from <= ?)")
                    base_params.append(at_time)
                    where_parts.append("(m.valid_until = '' OR m.valid_until >= ?)")
                    base_params.append(at_time)

                where_sql = " AND ".join(where_parts)
                base_params.append(limit)

                rows = conn.execute(
                    f"""
                    SELECT m.* FROM memories m
                    JOIN memories_fts f ON m.rowid = f.rowid
                    WHERE {where_sql}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    base_params,
                ).fetchall()
                return [MemoryEntry(**dict(row)) for row in rows]
            except Exception:
                pass

            # Fallback to LIKE search
            query = "SELECT * FROM memories WHERE content LIKE ?"
            params: list[Any] = [f"%{keyword}%"]
            if project:
                query += " AND project = ?"
                params.append(project)
            query += self._user_tenant_clause(params, user_id, tenant_id)
            query += self._at_time_clause(params, at_time)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [MemoryEntry(**dict(row)) for row in rows]
        finally:
            self._close(conn)

    def get_project_context(self, project: str) -> dict[str, Any]:
        conn = self._connection()
        try:
            row = conn.execute("SELECT context FROM projects WHERE name = ?", (project,)).fetchone()
            if row:
                return json.loads(row["context"])
            return {}
        finally:
            self._close(conn)

    def get_project_description(self, project: str) -> str:
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT description FROM projects WHERE name = ?", (project,)
            ).fetchone()
            return row["description"] if row and row["description"] else ""
        finally:
            self._close(conn)

    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
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

    def stats(self, user_id: str | None = None, tenant_id: str | None = None) -> dict[str, Any]:
        conn = self._connection()
        try:
            where = "WHERE 1=1"
            params: list[Any] = []
            if user_id is not None:
                where += " AND user_id = ?"
                params.append(user_id)
            if tenant_id is not None:
                where += " AND tenant_id = ?"
                params.append(tenant_id)

            total = conn.execute(f"SELECT COUNT(*) as c FROM memories {where}", params).fetchone()[
                "c"
            ]
            projects = conn.execute(
                f"SELECT COUNT(DISTINCT project) as c FROM memories {where}", params
            ).fetchone()["c"]
            sessions = conn.execute(
                f"SELECT COUNT(DISTINCT session_id) as c FROM memories {where}", params
            ).fetchone()["c"]
            categories = conn.execute(
                f"SELECT category, COUNT(*) as c FROM memories {where} GROUP BY category", params
            ).fetchall()
            return {
                "total_memories": total,
                "projects": projects,
                "sessions": sessions,
                "by_category": {row["category"]: row["c"] for row in categories},
            }
        finally:
            self._close(conn)

    def delete_project(
        self, project: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> int:
        conn = self._connection()
        try:
            query = "DELETE FROM memories WHERE project = ?"
            params: list[Any] = [project]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            if tenant_id is not None:
                query += " AND tenant_id = ?"
                params.append(tenant_id)
            cursor = conn.execute(query, params)
            conn.execute("DELETE FROM projects WHERE name = ?", (project,))
            conn.commit()
            return cursor.rowcount
        finally:
            self._close(conn)

    def store_embedding(self, memory_id: int, model_name: str, embedding: list[float]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connection()
        try:
            conn.execute(
                """
                INSERT INTO embeddings (memory_id, model_name, embedding_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    model_name=excluded.model_name,
                    embedding_json=excluded.embedding_json,
                    created_at=excluded.created_at
                """,
                (memory_id, model_name, json.dumps(embedding), now),
            )
            conn.commit()
        finally:
            self._close(conn)

    def get_embeddings(self, project: str, model_name: str) -> list[tuple[int, list[float]]]:
        conn = self._connection()
        try:
            rows = conn.execute(
                """
                SELECT e.memory_id, e.embedding_json
                FROM embeddings e
                JOIN memories m ON e.memory_id = m.id
                WHERE m.project = ? AND e.model_name = ?
                """,
                (project, model_name),
            ).fetchall()
            return [(row["memory_id"], json.loads(row["embedding_json"])) for row in rows]
        finally:
            self._close(conn)

    def list_embedding_models(self, project: str) -> list[str]:
        conn = self._connection()
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT e.model_name
                FROM embeddings e
                JOIN memories m ON e.memory_id = m.id
                WHERE m.project = ?
                """,
                (project,),
            ).fetchall()
            return [row["model_name"] for row in rows]
        finally:
            self._close(conn)

    def list_projects(self, user_id: str | None = None, tenant_id: str | None = None) -> list[str]:
        conn = self._connection()
        try:
            query = "SELECT DISTINCT project FROM memories WHERE 1=1"
            params: list[Any] = []
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            if tenant_id is not None:
                query += " AND tenant_id = ?"
                params.append(tenant_id)
            query += " ORDER BY project"
            rows = conn.execute(query, params).fetchall()
            return [row["project"] for row in rows]
        finally:
            self._close(conn)

    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        conn = self._connection()
        try:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row:
                return MemoryEntry(**dict(row))
            return None
        finally:
            self._close(conn)

    def update_memory(self, memory_id: int, updates: dict[str, Any]) -> bool:
        allowed = {
            "content",
            "category",
            "confidence",
            "tags",
            "user_id",
            "tenant_id",
            "valid_from",
            "valid_until",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not filtered:
            return False

        conn = self._connection()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in filtered)
            cursor = conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?",
                (*filtered.values(), memory_id),
            )
            if cursor.rowcount > 0 and "content" in filtered:
                self._fts5_delete(conn, memory_id)
                self._fts5_insert(conn, memory_id, filtered["content"])
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._close(conn)

    def delete_memory(self, memory_id: int) -> bool:
        conn = self._connection()
        try:
            self._fts5_delete(conn, memory_id)
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._close(conn)
