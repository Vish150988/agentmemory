"""Abstract base class for CrossAgentMemory storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..core import MemoryEntry


class MemoryBackend(ABC):
    """Abstract storage backend for memories."""

    @abstractmethod
    def init(self) -> None:
        """Initialize the backend (create tables, indexes, etc.)."""

    @abstractmethod
    def store(self, entry: MemoryEntry) -> int:
        """Store a memory entry. Returns the inserted ID."""

    @abstractmethod
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
        """Recall memories with optional filtering."""

    @abstractmethod
    def search(
        self,
        keyword: str,
        project: str | None = None,
        limit: int = 20,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
        """Keyword search over memory content."""

    @abstractmethod
    def get_project_context(self, project: str) -> dict[str, Any]:
        """Get stored project context."""

    @abstractmethod
    def get_project_description(self, project: str) -> str:
        """Get stored project description."""

    @abstractmethod
    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
        """Set or update project context."""

    @abstractmethod
    def stats(self, user_id: str | None = None, tenant_id: str | None = None) -> dict[str, Any]:
        """Return basic stats about the memory store."""

    @abstractmethod
    def delete_project(
        self, project: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> int:
        """Delete all memories for a project. Returns row count."""

    @abstractmethod
    def store_embedding(self, memory_id: int, model_name: str, embedding: list[float]) -> None:
        """Store a vector embedding for a memory."""

    @abstractmethod
    def get_embeddings(self, project: str, model_name: str) -> list[tuple[int, list[float]]]:
        """Retrieve all embeddings for a project matching a model."""

    @abstractmethod
    def list_embedding_models(self, project: str) -> list[str]:
        """Return all distinct embedding model names for a project."""

    @abstractmethod
    def list_projects(self, user_id: str | None = None, tenant_id: str | None = None) -> list[str]:
        """Return a list of all distinct project names."""

    @abstractmethod
    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        """Get a single memory by ID."""

    @abstractmethod
    def update_memory(self, memory_id: int, updates: dict[str, Any]) -> bool:
        """Update fields of an existing memory. Returns True if found."""

    @abstractmethod
    def recall_temporal(
        self,
        project: str | None = None,
        at_time: str | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Recall memories with explicit temporal window filtering."""

    @abstractmethod
    def delete_memory(self, memory_id: int) -> bool:
        """Delete a single memory by ID. Returns True if deleted."""
