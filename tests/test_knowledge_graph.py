"""Tests for the lightweight knowledge graph module."""

from __future__ import annotations

from pathlib import Path

from crossagentmemory.core import MemoryEngine, MemoryEntry
from crossagentmemory.knowledge_graph import (
    delete_graph_for_project,
    extract_and_store_for_memory,
    find_paths,
    get_graph_for_project,
    get_nodes,
    get_related_memories,
    init_graph_schema,
    store_extraction,
)


def test_init_graph_schema(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)
    # Should be idempotent
    init_graph_schema(db)


def test_store_extraction_and_query(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)

    extraction = {
        "entities": [
            {"name": "React", "type": "technology"},
            {"name": "Zustand", "type": "library"},
        ],
        "relations": [
            {"source": "React", "target": "Zustand", "relation": "uses"},
        ],
    }
    result = store_extraction("proj", 1, extraction, db_path=db)
    assert result["nodes"] == 2
    assert result["edges"] == 1

    # Idempotent: same extraction again should create no new rows
    result2 = store_extraction("proj", 1, extraction, db_path=db)
    assert result2["nodes"] == 0
    assert result2["edges"] == 0

    graph = get_graph_for_project("proj", db_path=db)
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["relation"] == "uses"


def test_get_nodes_filter_by_type(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)
    store_extraction(
        "p",
        1,
        {
            "entities": [
                {"name": "Redux", "type": "library"},
                {"name": "Team A", "type": "team"},
            ],
            "relations": [],
        },
        db_path=db,
    )
    libs = get_nodes("p", node_type="library", db_path=db)
    assert len(libs) == 1
    assert libs[0].name == "Redux"


def test_find_paths(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)
    store_extraction(
        "p",
        1,
        {
            "entities": [
                {"name": "A", "type": "concept"},
                {"name": "B", "type": "concept"},
                {"name": "C", "type": "concept"},
            ],
            "relations": [
                {"source": "A", "target": "B", "relation": "led_to"},
                {"source": "B", "target": "C", "relation": "led_to"},
            ],
        },
        db_path=db,
    )
    paths = find_paths("p", "A", "C", max_depth=5, db_path=db)
    assert len(paths) == 1
    assert len(paths[0]) == 2


def test_find_paths_no_match(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)
    paths = find_paths("p", "X", "Y", db_path=db)
    assert paths == []


def test_delete_graph_for_project(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    init_graph_schema(db)
    store_extraction(
        "p",
        1,
        {
            "entities": [{"name": "X", "type": "concept"}],
            "relations": [],
        },
        db_path=db,
    )
    count = delete_graph_for_project("p", db_path=db)
    assert count == 1
    graph = get_graph_for_project("p", db_path=db)
    assert graph["nodes"] == []


def test_get_related_memories(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    engine = MemoryEngine(db_path=db)
    mid = engine.store(MemoryEntry(project="p", session_id="s", content="auth with JWT"))
    store_extraction(
        "p",
        mid,
        {
            "entities": [
                {"name": "JWT", "type": "technology"},
                {"name": "Auth", "type": "concept"},
            ],
            "relations": [
                {"source": "Auth", "target": "JWT", "relation": "uses"},
            ],
        },
        db_path=db,
    )
    rels = get_related_memories("p", "JWT", db_path=db)
    assert len(rels) >= 1


def test_extract_and_store_for_memory_with_mock_llm(tmp_path: Path) -> None:
    """Test with a fake LLM client that returns predictable JSON."""

    class FakeClient:
        def is_available(self):
            return True

        def chat(self, prompt, system=""):
            from crossagentmemory.llm import LLMResponse

            return LLMResponse(
                text='{"entities": [{"name": "Docker", "type": "technology"}], "relations": []}',
                model="fake",
                provider="fake",
            )

    db = tmp_path / "kg.db"
    result = extract_and_store_for_memory(
        "p", 42, "We containerize with Docker", db_path=db, client=FakeClient()
    )
    assert result["nodes"] == 1
    assert result["edges"] == 0
    nodes = get_nodes("p", db_path=db)
    assert any(n.name == "Docker" for n in nodes)
