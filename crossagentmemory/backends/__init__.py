"""Pluggable storage backends for CrossAgentMemory."""

from __future__ import annotations

from .base import MemoryBackend
from .sqlite import SQLiteBackend

try:
    from .postgres import PostgresBackend
except ImportError:
    PostgresBackend = None  # type: ignore[assignment,misc]

try:
    from .chroma import ChromaBackend
except ImportError:
    ChromaBackend = None  # type: ignore[assignment,misc]

try:
    from .redis import RedisBackend
except ImportError:
    RedisBackend = None  # type: ignore[assignment,misc]

__all__ = ["MemoryBackend", "SQLiteBackend", "PostgresBackend", "ChromaBackend", "RedisBackend"]
