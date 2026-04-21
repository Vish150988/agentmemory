"""Tests for memory decay and reinforcement."""

import tempfile
from pathlib import Path

from agentmemory.core import MemoryEngine, MemoryEntry
from agentmemory.decay import decay_confidence, reinforce_memory


def test_reinforce_memory():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        mid = engine.store(MemoryEntry(project="p", session_id="s", content="test", confidence=0.5))
        assert reinforce_memory(engine, mid, boost=0.2) is True

        # Verify boost
        memories = engine.recall(project="p")
        assert memories[0].confidence == 0.7


def test_reinforce_nonexistent_memory():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)
        assert reinforce_memory(engine, 99999, boost=0.1) is False


def test_decay_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="recent memory",
                confidence=1.0,
            )
        )

        stats = decay_confidence(engine, project="p", half_life_days=30.0, dry_run=True)
        assert stats["total_processed"] == 1
        # Recent memory should be unchanged in dry run
        assert stats["updated"] == 0


def test_decay_affects_old_memories():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        engine = MemoryEngine(db_path=db_path)

        # Store with a very old timestamp
        old_time = "2025-01-01T00:00:00+00:00"
        engine.store(
            MemoryEntry(
                project="p",
                session_id="s",
                content="old memory",
                confidence=1.0,
                timestamp=old_time,
            )
        )

        stats = decay_confidence(engine, project="p", half_life_days=1.0, dry_run=False)
        assert stats["total_processed"] == 1
        assert stats["updated"] == 1

        # Verify confidence dropped
        memories = engine.recall(project="p")
        assert memories[0].confidence < 1.0
