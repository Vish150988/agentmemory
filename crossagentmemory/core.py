"""Core memory engine backed by pluggable storage backends."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_MEMORY_DIR = Path.home() / ".crossagentmemory"
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


def _resolve_backend(backend: str, db_path: Path | None = None):
    """Resolve a backend name to a backend instance."""
    from .backends import SQLiteBackend

    if backend == "auto":
        if os.environ.get("DATABASE_URL"):
            try:
                from .backends import PostgresBackend

                return PostgresBackend()
            except ImportError:
                pass
        return SQLiteBackend(db_path)
    if backend == "sqlite":
        return SQLiteBackend(db_path)
    if backend == "postgres":
        from .backends import PostgresBackend

        return PostgresBackend()
    if backend == "chroma":
        from .backends import ChromaBackend

        return ChromaBackend()
    if backend == "redis":
        from .backends import RedisBackend

        return RedisBackend()
    raise ValueError(f"Unknown backend: {backend}")


class MemoryEngine:
    """Memory engine that delegates to a pluggable storage backend."""

    def __init__(self, db_path: Optional[Path] = None, backend: Optional[str] = None):
        from .config import resolve_backend_from_config

        cfg = resolve_backend_from_config()
        resolved_backend = backend or cfg.get("backend", "auto")
        resolved_db_path = db_path or cfg.get("db_path")
        self.db_path = resolved_db_path or DEFAULT_DB_PATH
        self.backend = _resolve_backend(resolved_backend, resolved_db_path)
        self.backend.init()

    def store(self, entry: MemoryEntry) -> int:
        """Store a memory entry. Returns the inserted row ID."""
        return self.backend.store(entry)

    def recall(
        self,
        project: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        session_id: Optional[str] = None,
    ) -> list[MemoryEntry]:
        """Recall memories with optional filtering."""
        return self.backend.recall(project, category, limit, session_id)

    def search(
        self,
        keyword: str,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Simple keyword search over memory content."""
        return self.backend.search(keyword, project, limit)

    def get_project_context(self, project: str) -> dict[str, Any]:
        """Get stored project context."""
        return self.backend.get_project_context(project)

    def get_project_description(self, project: str) -> str:
        """Get stored project description."""
        return self.backend.get_project_description(project)

    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
        """Set or update project context."""
        self.backend.set_project_context(project, context, description)

    def stats(self) -> dict[str, Any]:
        """Return basic stats about the memory store."""
        return self.backend.stats()

    def delete_project(self, project: str) -> int:
        """Delete all memories for a project. Returns number of rows deleted."""
        return self.backend.delete_project(project)

    def store_embedding(
        self, memory_id: int, model_name: str, embedding: list[float]
    ) -> None:
        """Store a vector embedding for a memory."""
        self.backend.store_embedding(memory_id, model_name, embedding)

    def get_embeddings(
        self, project: str, model_name: str
    ) -> list[tuple[int, list[float]]]:
        """Retrieve all embeddings for a project matching a model."""
        return self.backend.get_embeddings(project, model_name)

    def list_embedding_models(self, project: str) -> list[str]:
        """Return all distinct embedding model names for a project."""
        return self.backend.list_embedding_models(project)

    def list_projects(self) -> list[str]:
        """Return a list of all distinct project names."""
        return self.backend.list_projects()

    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        """Get a single memory by ID."""
        return self.backend.get_memory_by_id(memory_id)

    def update_memory(self, memory_id: int, updates: dict[str, Any]) -> bool:
        """Update fields of an existing memory. Returns True if found."""
        return self.backend.update_memory(memory_id, updates)

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a single memory by ID. Returns True if deleted."""
        return self.backend.delete_memory(memory_id)
