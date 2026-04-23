"""CrossAgentMemory — Open-source cross-agent memory layer for AI coding agents."""

__version__ = "0.4.0"

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

try:
    from .backends import ChromaBackend  # noqa: F401

    __all__.append("ChromaBackend")
except ImportError:
    pass

try:
    from .backends import RedisBackend  # noqa: F401

    __all__.append("RedisBackend")
except ImportError:
    pass
