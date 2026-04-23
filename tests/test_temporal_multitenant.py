"""Tests for temporal reasoning and multi-tenancy features."""

import tempfile
from pathlib import Path

from crossagentmemory.core import MemoryEngine, MemoryEntry


class TestTemporalReasoning:
    """Test validity windows and temporal recall."""

    def test_store_with_validity_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            entry = MemoryEntry(
                project="proj",
                session_id="s1",
                content="Used Redux for state management",
                valid_from="2024-01-01T00:00:00+00:00",
                valid_until="2024-03-15T00:00:00+00:00",
            )
            mid = engine.store(entry)
            assert mid > 0

            recalled = engine.get_memory_by_id(mid)
            assert recalled is not None
            assert recalled.valid_from == "2024-01-01T00:00:00+00:00"
            assert recalled.valid_until == "2024-03-15T00:00:00+00:00"

    def test_recall_at_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            # Memory valid Jan 1 - Mar 15
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Used Redux",
                    valid_from="2024-01-01T00:00:00+00:00",
                    valid_until="2024-03-15T00:00:00+00:00",
                )
            )
            # Memory valid Mar 15 onwards
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Switched to Zustand",
                    valid_from="2024-03-15T00:00:00+00:00",
                    valid_until="",
                )
            )
            # Always valid memory
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Always true fact",
                )
            )

            # Query at Feb 1 — should get Redux + always-true
            results = engine.recall(project="proj", at_time="2024-02-01T00:00:00+00:00")
            contents = {r.content for r in results}
            assert "Used Redux" in contents
            assert "Always true fact" in contents
            assert "Switched to Zustand" not in contents

            # Query at Mar 20 — should get Zustand + always-true
            results = engine.recall(project="proj", at_time="2024-03-20T00:00:00+00:00")
            contents = {r.content for r in results}
            assert "Switched to Zustand" in contents
            assert "Always true fact" in contents
            assert "Used Redux" not in contents

    def test_recall_temporal_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Q1 initiative",
                    valid_from="2024-01-01T00:00:00+00:00",
                    valid_until="2024-03-31T00:00:00+00:00",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Q2 initiative",
                    valid_from="2024-04-01T00:00:00+00:00",
                    valid_until="2024-06-30T00:00:00+00:00",
                )
            )

            # Window overlapping Q1 and Q2
            results = engine.recall_temporal(
                project="proj",
                window_start="2024-03-15T00:00:00+00:00",
                window_end="2024-04-15T00:00:00+00:00",
            )
            contents = {r.content for r in results}
            assert "Q1 initiative" in contents
            assert "Q2 initiative" in contents

            # Window fully in Q1
            results = engine.recall_temporal(
                project="proj",
                window_start="2024-02-01T00:00:00+00:00",
                window_end="2024-02-28T00:00:00+00:00",
            )
            contents = {r.content for r in results}
            assert "Q1 initiative" in contents
            assert "Q2 initiative" not in contents

    def test_search_with_at_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="old auth system",
                    valid_from="2023-01-01T00:00:00+00:00",
                    valid_until="2023-12-31T00:00:00+00:00",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="new auth system",
                    valid_from="2024-01-01T00:00:00+00:00",
                    valid_until="",
                )
            )

            results = engine.search("auth", project="proj", at_time="2023-06-01T00:00:00+00:00")
            assert len(results) == 1
            assert results[0].content == "old auth system"

            results = engine.search("auth", project="proj", at_time="2024-06-01T00:00:00+00:00")
            assert len(results) == 1
            assert results[0].content == "new auth system"


class TestMultiTenancy:
    """Test user_id and tenant_id isolation."""

    def test_recall_isolated_by_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Alice's memory",
                    user_id="alice",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Bob's memory",
                    user_id="bob",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Shared memory",
                    user_id="",
                )
            )

            alice_results = engine.recall(project="proj", user_id="alice")
            assert len(alice_results) == 1
            assert alice_results[0].content == "Alice's memory"

            bob_results = engine.recall(project="proj", user_id="bob")
            assert len(bob_results) == 1
            assert bob_results[0].content == "Bob's memory"

    def test_recall_isolated_by_tenant(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Acme Corp memory",
                    tenant_id="acme",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Globex memory",
                    tenant_id="globex",
                )
            )

            acme_results = engine.recall(project="proj", tenant_id="acme")
            assert len(acme_results) == 1
            assert acme_results[0].content == "Acme Corp memory"

    def test_combined_user_and_tenant(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Alice at Acme",
                    user_id="alice",
                    tenant_id="acme",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Alice at Globex",
                    user_id="alice",
                    tenant_id="globex",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Bob at Acme",
                    user_id="bob",
                    tenant_id="acme",
                )
            )

            results = engine.recall(project="proj", user_id="alice", tenant_id="acme")
            assert len(results) == 1
            assert results[0].content == "Alice at Acme"

    def test_stats_per_tenant(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(MemoryEntry(project="proj", session_id="s1", content="A", tenant_id="t1"))
            engine.store(MemoryEntry(project="proj", session_id="s1", content="B", tenant_id="t1"))
            engine.store(MemoryEntry(project="proj", session_id="s1", content="C", tenant_id="t2"))

            t1_stats = engine.stats(tenant_id="t1")
            assert t1_stats["total_memories"] == 2

            t2_stats = engine.stats(tenant_id="t2")
            assert t2_stats["total_memories"] == 1

    def test_delete_project_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(project="proj", session_id="s1", content="Alice", user_id="alice")
            )
            engine.store(MemoryEntry(project="proj", session_id="s1", content="Bob", user_id="bob"))

            deleted = engine.delete_project("proj", user_id="alice")
            assert deleted == 1

            remaining = engine.recall(project="proj")
            assert len(remaining) == 1
            assert remaining[0].content == "Bob"

    def test_list_projects_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(MemoryEntry(project="p1", session_id="s1", content="A", user_id="alice"))
            engine.store(MemoryEntry(project="p2", session_id="s1", content="B", user_id="bob"))

            alice_projects = engine.list_projects(user_id="alice")
            assert alice_projects == ["p1"]

            bob_projects = engine.list_projects(user_id="bob")
            assert bob_projects == ["p2"]


class TestTemporalAndMultiTenancyCombined:
    """Test combined temporal + multi-tenant queries."""

    def test_recall_at_time_with_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = MemoryEngine(db_path=db_path)

            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Alice old fact",
                    user_id="alice",
                    valid_from="2024-01-01T00:00:00+00:00",
                    valid_until="2024-02-01T00:00:00+00:00",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Alice new fact",
                    user_id="alice",
                    valid_from="2024-02-01T00:00:00+00:00",
                    valid_until="",
                )
            )
            engine.store(
                MemoryEntry(
                    project="proj",
                    session_id="s1",
                    content="Bob fact",
                    user_id="bob",
                    valid_from="2024-01-01T00:00:00+00:00",
                    valid_until="",
                )
            )

            results = engine.recall(
                project="proj",
                user_id="alice",
                at_time="2024-03-01T00:00:00+00:00",
            )
            assert len(results) == 1
            assert results[0].content == "Alice new fact"
