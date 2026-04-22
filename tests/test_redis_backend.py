"""Tests for Redis backend."""

from __future__ import annotations

import uuid

import pytest

from crossagentmemory import MemoryEntry
from crossagentmemory.backends.redis import RedisBackend


@pytest.fixture
def redis_backend():
    try:
        backend = RedisBackend()
        backend.init()
    except Exception:
        pytest.skip("Redis not available")
    # Use a unique prefix to avoid cross-test contamination
    prefix = f"cam:test:{uuid.uuid4().hex}:"
    # Patch the key prefix for isolation
    import crossagentmemory.backends.redis as redis_mod

    original_prefix = redis_mod.KEY_PREFIX
    redis_mod.KEY_PREFIX = prefix
    yield backend
    # Cleanup
    r = backend._client()
    for key in r.scan_iter(match=f"{prefix}*"):
        r.delete(key)
    redis_mod.KEY_PREFIX = original_prefix


def test_redis_store_and_recall(redis_backend):
    entry = MemoryEntry(project="test", content="hello redis", category="fact")
    mid = redis_backend.store(entry)
    assert mid is not None
    results = redis_backend.recall(project="test")
    assert len(results) == 1
    assert results[0].content == "hello redis"


def test_redis_search(redis_backend):
    redis_backend.store(MemoryEntry(project="p", content="machine learning"))
    redis_backend.store(MemoryEntry(project="p", content="deep learning"))
    results = redis_backend.search("machine", project="p")
    assert len(results) == 1
    assert results[0].content == "machine learning"


def test_redis_project_context(redis_backend):
    redis_backend.set_project_context("p1", {"key": "val"}, "desc")
    assert redis_backend.get_project_description("p1") == "desc"
    assert redis_backend.get_project_context("p1") == {"key": "val"}


def test_redis_stats(redis_backend):
    redis_backend.store(MemoryEntry(project="x", content="a"))
    redis_backend.store(MemoryEntry(project="x", content="b"))
    stats = redis_backend.stats()
    assert stats["total_memories"] == 2


def test_redis_delete_project(redis_backend):
    redis_backend.store(MemoryEntry(project="del", content="gone"))
    count = redis_backend.delete_project("del")
    assert count == 1
    assert redis_backend.recall(project="del") == []


def test_redis_get_and_update_memory(redis_backend):
    mid = redis_backend.store(MemoryEntry(project="u", content="before"))
    entry = redis_backend.get_memory_by_id(mid)
    assert entry is not None
    assert entry.content == "before"
    ok = redis_backend.update_memory(mid, {"content": "after"})
    assert ok
    updated = redis_backend.get_memory_by_id(mid)
    assert updated.content == "after"


def test_redis_delete_memory(redis_backend):
    mid = redis_backend.store(MemoryEntry(project="d", content="delete me"))
    assert redis_backend.delete_memory(mid)
    assert redis_backend.get_memory_by_id(mid) is None


def test_redis_list_projects(redis_backend):
    redis_backend.store(MemoryEntry(project="p1", content="a"))
    redis_backend.store(MemoryEntry(project="p2", content="b"))
    projects = redis_backend.list_projects()
    assert "p1" in projects
    assert "p2" in projects


def test_redis_embeddings(redis_backend):
    mid = redis_backend.store(MemoryEntry(project="emb", content="vector"))
    redis_backend.store_embedding(mid, "test-model", [0.1, 0.2, 0.3])
    models = redis_backend.list_embedding_models("emb")
    assert "test-model" in models
    embs = redis_backend.get_embeddings("emb", "test-model")
    assert len(embs) == 1
    assert embs[0][0] == mid
    assert embs[0][1] == [0.1, 0.2, 0.3]
