"""Tests for auto conflict resolution."""

from __future__ import annotations

from pathlib import Path

from crossagentmemory.conflict_resolution import (
    _llm_resolve_conflict,
    auto_resolve_conflicts,
    find_contradictions_for_memory,
    scan_and_resolve_project,
)
from crossagentmemory.core import MemoryEngine, MemoryEntry


def test_find_contradictions_with_mock_llm(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    # Seed enough memories for TF-IDF to produce meaningful similarities
    engine.store(MemoryEntry(project="p", session_id="s", content="Setup webpack config"))
    engine.store(MemoryEntry(project="p", session_id="s", content="Configured Jest for testing"))
    engine.store(MemoryEntry(project="p", session_id="s", content="Added ESLint rules"))
    engine.store(
        MemoryEntry(
            project="p", session_id="s", content="We use Redux for global state management",
            category="decision",
        )
    )
    mid2 = engine.store(
        MemoryEntry(
            project="p", session_id="s", content="We use Zustand for global state management",
            category="decision",
        )
    )

    class FakeClient:
        def is_available(self):
            return True

        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='{"is_contradiction": true, "outdated": "b", "reason": "Migrated away"}',
                model="fake",
                provider="fake",
            )

    new_mem = engine.get_memory_by_id(mid2)
    assert new_mem is not None
    result = find_contradictions_for_memory(engine, new_mem, threshold=0.01, client=FakeClient())
    assert len(result) > 0
    assert result[0]["contradiction_verdict"]["is_contradiction"] is True


def test_auto_resolve_conflicts_decay(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    mid1 = engine.store(
        MemoryEntry(
            project="p", session_id="s", content="Use Redux", confidence=0.95
        )
    )
    mid2 = engine.store(
        MemoryEntry(project="p", session_id="s", content="Use Zustand instead")
    )

    class FakeClient:
        def is_available(self):
            return True

        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='{"is_contradiction": true, "outdated": "b", "reason": "Switched"}',
                model="fake",
                provider="fake",
            )

    new_mem = engine.get_memory_by_id(mid2)
    assert new_mem is not None
    actions = auto_resolve_conflicts(
        engine, new_mem, strategy="decay", decay_amount=0.3, client=FakeClient()
    )
    assert len(actions) > 0
    updated = engine.get_memory_by_id(mid1)
    assert updated is not None
    assert updated.confidence == 0.65


def test_auto_resolve_conflicts_expire(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    mid1 = engine.store(
        MemoryEntry(project="p", session_id="s", content="Deploy to Heroku")
    )
    mid2 = engine.store(
        MemoryEntry(project="p", session_id="s", content="Deploy to Vercel")
    )

    class FakeClient:
        def is_available(self):
            return True

        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='{"is_contradiction": true, "outdated": "b", "reason": "Moved"}',
                model="fake",
                provider="fake",
            )

    new_mem = engine.get_memory_by_id(mid2)
    assert new_mem is not None
    actions = auto_resolve_conflicts(
        engine, new_mem, strategy="expire", client=FakeClient()
    )
    assert len(actions) > 0
    updated = engine.get_memory_by_id(mid1)
    assert updated is not None
    assert updated.valid_until != ""


def test_llm_resolve_conflict_parsing() -> None:
    class FakeClient:
        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='```json\n{"is_contradiction": true, "outdated": "b", "reason": "r"}\n```',
                model="fake",
                provider="fake",
            )

    result = _llm_resolve_conflict("a", "b", FakeClient())
    assert result is not None
    assert result["is_contradiction"] is True
    assert result["outdated"] == "b"


def test_scan_and_resolve_project(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    engine = MemoryEngine(db_path=db)
    engine.store(MemoryEntry(project="p", session_id="s", content="Use jQuery"))
    engine.store(MemoryEntry(project="p", session_id="s", content="Use React"))

    class FakeClient:
        def is_available(self):
            return True

        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='{"is_contradiction": true, "outdated": "a", "reason": "Modernized"}',
                model="fake",
                provider="fake",
            )

    actions = scan_and_resolve_project(engine, "p", strategy="decay", client=FakeClient())
    assert len(actions) > 0
