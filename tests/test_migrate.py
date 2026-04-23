"""Tests for backend migration."""

from __future__ import annotations

from pathlib import Path

from crossagentmemory import MemoryEngine, MemoryEntry


class TestMigrate:
    def test_migrate_sqlite_to_sqlite(self, tmp_path: Path) -> None:
        """Migrate memories from one SQLite DB to another."""
        source_db = tmp_path / "source.db"
        target_db = tmp_path / "target.db"

        source = MemoryEngine(db_path=source_db, backend="sqlite")
        entry = MemoryEntry(
            project="test-proj",
            category="decision",
            content="Use Postgres",
            confidence=0.95,
        )
        source.store(entry)
        source.set_project_context("test-proj", {"key": "value"}, description="desc")

        target = MemoryEngine(db_path=target_db, backend="sqlite")

        # Perform migration manually (simulate CLI logic)
        memories = source.recall(limit=100_000)
        id_map: dict[int, int] = {}
        for m in memories:
            old_id = m.id
            m.id = None
            new_id = target.store(m)
            if old_id is not None:
                id_map[old_id] = new_id

        for proj in source.list_projects():
            ctx = source.get_project_context(proj)
            desc = source.get_project_description(proj)
            if ctx or desc:
                target.set_project_context(proj, ctx, description=desc)

        assert len(target.recall(project="test-proj")) == 1
        assert target.get_project_context("test-proj") == {"key": "value"}
        assert target.get_project_description("test-proj") == "desc"

    def test_migrate_preserves_embeddings(self, tmp_path: Path) -> None:
        """Embeddings should be transferable across backends."""
        source_db = tmp_path / "source.db"
        target_db = tmp_path / "target.db"

        source = MemoryEngine(db_path=source_db, backend="sqlite")
        eid = source.store(MemoryEntry(project="proj", content="hello", category="fact"))
        source.store_embedding(eid, "tfidf", [0.1, 0.2, 0.3])

        target = MemoryEngine(db_path=target_db, backend="sqlite")

        memories = source.recall(limit=100_000)
        id_map: dict[int, int] = {}
        for m in memories:
            old_id = m.id
            m.id = None
            new_id = target.store(m)
            if old_id is not None:
                id_map[old_id] = new_id

        for proj in source.list_projects():
            for model_name in ("tfidf", "sentence-transformers"):
                embeddings = source.get_embeddings(proj, model_name)
                for old_id, emb in embeddings:
                    new_id = id_map.get(old_id)
                    if new_id:
                        target.store_embedding(new_id, model_name, emb)

        embs = target.get_embeddings("proj", "tfidf")
        assert len(embs) == 1
        assert embs[0][1] == [0.1, 0.2, 0.3]
