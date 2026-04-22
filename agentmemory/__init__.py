"""AgentMemory — Open-source cross-agent memory layer for AI coding agents."""

__version__ = "0.3.6"

from .backends import MemoryBackend, SQLiteBackend
from .core import MemoryEngine, MemoryEntry

__all__ = [
    "MemoryEngine",
    "MemoryEntry",
    "MemoryBackend",
    "SQLiteBackend",
]

try:
    from .backends import PostgresBackend  # noqa: F401
    __all__.append("PostgresBackend")
except ImportError:
    pass
