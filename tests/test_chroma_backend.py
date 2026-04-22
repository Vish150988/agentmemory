"""Tests for ChromaDB backend."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from crossagentmemory import MemoryEntry
from crossagentmemory.backends.chroma import ChromaBackend


@pytest.fixture
def chroma_backend():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        backend = ChromaBackend(persist_dir=Path(tmpdir))
        backend.init()
        yield backend


def test_chroma_store_and_recall(chroma_backend):
    entry = MemoryEntry(project="test", content="hello chroma", category="fact")
    mid = chroma_backend.store(entry)
    assert mid is not None
    results = chroma_backend.recall(project="test")
    assert len(results) == 1
    assert results[0].content == "hello chroma"


def test_chroma_search(chroma_backend):
    chroma_backend.store(MemoryEntry(project="p", content="machine learning"))
    chroma_backend.store(MemoryEntry(project="p", content="deep learning"))
    results = chroma_backend.search("machine", project="p")
    assert len(results) == 1
    assert results[0].content == "machine learning"


def test_chroma_project_context(chroma_backend):
    chroma_backend.set_project_context("p1", {"key": "val"}, "desc")
    assert chroma_backend.get_project_description("p1") == "desc"
    assert chroma_backend.get_project_context("p1") == {"key": "val"}


def test_chroma_stats(chroma_backend):
    chroma_backend.store(MemoryEntry(project="x", content="a"))
    chroma_backend.store(MemoryEntry(project="x", content="b"))
    stats = chroma_backend.stats()
    assert stats["total_memories"] == 2


def test_chroma_delete_project(chroma_backend):
    chroma_backend.store(MemoryEntry(project="del", content="gone"))
    count = chroma_backend.delete_project("del")
    assert count == 1
    assert chroma_backend.recall(project="del") == []


def test_chroma_get_and_update_memory(chroma_backend):
    mid = chroma_backend.store(MemoryEntry(project="u", content="before"))
    entry = chroma_backend.get_memory_by_id(mid)
    assert entry is not None
    assert entry.content == "before"
    ok = chroma_backend.update_memory(mid, {"content": "after"})
    assert ok
    updated = chroma_backend.get_memory_by_id(mid)
    assert updated.content == "after"


def test_chroma_delete_memory(chroma_backend):
    mid = chroma_backend.store(MemoryEntry(project="d", content="delete me"))
    assert chroma_backend.delete_memory(mid)
    assert chroma_backend.get_memory_by_id(mid) is None


def test_chroma_list_projects(chroma_backend):
    chroma_backend.store(MemoryEntry(project="p1", content="a"))
    chroma_backend.store(MemoryEntry(project="p2", content="b"))
    projects = chroma_backend.list_projects()
    assert "p1" in projects
    assert "p2" in projects


def test_chroma_embeddings(chroma_backend):
    mid = chroma_backend.store(MemoryEntry(project="emb", content="vector"))
    chroma_backend.store_embedding(mid, "test-model", [0.1] * 384)
    models = chroma_backend.list_embedding_models("emb")
    assert "test-model" in models
    embs = chroma_backend.get_embeddings("emb", "test-model")
    assert len(embs) == 1
    assert embs[0][0] == mid
