"""Redis storage backend for CrossAgentMemory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..core import MemoryEntry
from .base import MemoryBackend

KEY_PREFIX = "cam"


class RedisBackend(MemoryBackend):
    """Redis-backed memory storage."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self._host = host
        self._port = port
        self._db = db
        self._redis = None

    def _client(self):
        if self._redis is None:
            import redis as redis_lib

            self._redis = redis_lib.Redis(
                host=self._host, port=self._port, db=self._db, decode_responses=True
            )
        return self._redis

    def init(self) -> None:
        self._client().ping()

    def _memory_key(self, memory_id: int) -> str:
        return f"{KEY_PREFIX}:memory:{memory_id}"

    def _project_zset(self, project: str) -> str:
        return f"{KEY_PREFIX}:project:{project}"

    def _project_meta(self, project: str) -> str:
        return f"{KEY_PREFIX}:project:{project}:meta"

    def _embedding_key(self, memory_id: int, model_name: str) -> str:
        return f"{KEY_PREFIX}:embedding:{memory_id}:{model_name}"

    def store(self, entry: MemoryEntry) -> int:
        r = self._client()
        if entry.id is None:
            entry.id = int(r.incr(f"{KEY_PREFIX}:seq"))
        if not entry.timestamp:
            entry.timestamp = datetime.now(timezone.utc).isoformat()
        key = self._memory_key(entry.id)
        r.hset(
            key,
            mapping={
                "id": str(entry.id),
                "project": entry.project,
                "session_id": entry.session_id or "",
                "timestamp": entry.timestamp,
                "category": entry.category,
                "content": entry.content,
                "confidence": str(entry.confidence),
                "source": entry.source or "",
                "tags": entry.tags or "",
                "metadata": entry.metadata or "{}",
                "user_id": entry.user_id or "",
                "tenant_id": entry.tenant_id or "",
                "valid_from": entry.valid_from or "",
                "valid_until": entry.valid_until or "",
            },
        )
        r.sadd(f"{KEY_PREFIX}:projects", entry.project)
        r.zadd(self._project_zset(entry.project), {str(entry.id): entry.timestamp})
        return entry.id

    def recall(
        self,
        project: str | None = None,
        category: str | None = None,
        limit: int = 50,
        session_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
        r = self._client()
        ids: list[str] = []
        if project:
            ids = r.zrevrange(self._project_zset(project), 0, limit - 1)
        else:
            # Scan all memory keys
            for key in r.scan_iter(match=f"{KEY_PREFIX}:memory:*"):
                ids.append(key.split(":")[-1])
            ids = ids[:limit]

        entries = [self._load(r, int(mid)) for mid in ids]
        entries = [e for e in entries if e is not None]
        if category:
            entries = [e for e in entries if e.category == category]
        if session_id:
            entries = [e for e in entries if e.session_id == session_id]
        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        if tenant_id is not None:
            entries = [e for e in entries if e.tenant_id == tenant_id]
        if at_time is not None:
            entries = [
                e
                for e in entries
                if (not e.valid_from or e.valid_from <= at_time)
                and (not e.valid_until or e.valid_until >= at_time)
            ]
        return entries

    def recall_temporal(
        self,
        project: str | None = None,
        at_time: str | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        r = self._client()
        ids: list[str] = []
        if project:
            ids = r.zrevrange(self._project_zset(project), 0, limit - 1)
        else:
            for key in r.scan_iter(match=f"{KEY_PREFIX}:memory:*"):
                ids.append(key.split(":")[-1])
            ids = ids[:limit]

        entries = [self._load(r, int(mid)) for mid in ids]
        entries = [e for e in entries if e is not None]
        if at_time is not None:
            entries = [
                e
                for e in entries
                if (not e.valid_from or e.valid_from <= at_time)
                and (not e.valid_until or e.valid_until >= at_time)
            ]
        if window_start is not None and window_end is not None:
            entries = [
                e
                for e in entries
                if (not e.valid_until or e.valid_until >= window_start)
                and (not e.valid_from or e.valid_from <= window_end)
            ]
        return entries

    def search(
        self,
        keyword: str,
        project: str | None = None,
        limit: int = 20,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
        r = self._client()
        results: list[MemoryEntry] = []
        for key in r.scan_iter(match=f"{KEY_PREFIX}:memory:*"):
            data = r.hgetall(key)
            if keyword.lower() in data.get("content", "").lower():
                if project and data.get("project") != project:
                    continue
                entry = self._entry_from_hash(data)
                if entry is None:
                    continue
                if user_id is not None and entry.user_id != user_id:
                    continue
                if tenant_id is not None and entry.tenant_id != tenant_id:
                    continue
                if at_time is not None:
                    if not (
                        (not entry.valid_from or entry.valid_from <= at_time)
                        and (not entry.valid_until or entry.valid_until >= at_time)
                    ):
                        continue
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_project_context(self, project: str) -> dict[str, Any]:
        r = self._client()
        raw = r.hget(self._project_meta(project), "context")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def get_project_description(self, project: str) -> str:
        r = self._client()
        return r.hget(self._project_meta(project), "description") or ""

    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
        r = self._client()
        r.hset(
            self._project_meta(project),
            mapping={
                "context": json.dumps(context),
                "description": description,
            },
        )
        r.sadd(f"{KEY_PREFIX}:projects", project)

    def stats(self, user_id: str | None = None, tenant_id: str | None = None) -> dict[str, Any]:
        r = self._client()
        count = 0
        for key in r.scan_iter(match=f"{KEY_PREFIX}:memory:*"):
            data = r.hgetall(key)
            if user_id is not None and data.get("user_id") != user_id:
                continue
            if tenant_id is not None and data.get("tenant_id") != tenant_id:
                continue
            count += 1
        return {"total_memories": count}

    def delete_project(
        self, project: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> int:
        r = self._client()
        ids = r.zrange(self._project_zset(project), 0, -1)
        pipe = r.pipeline()
        deleted = 0
        for mid in ids:
            data = r.hgetall(self._memory_key(int(mid)))
            if not data or data.get("project") != project:
                continue
            if user_id is not None and data.get("user_id") != user_id:
                continue
            if tenant_id is not None and data.get("tenant_id") != tenant_id:
                continue
            pipe.delete(self._memory_key(int(mid)))
            # Also delete any embeddings
            for emb_key in r.scan_iter(match=f"{KEY_PREFIX}:embedding:{mid}:*"):
                pipe.delete(emb_key)
            pipe.zrem(self._project_zset(project), mid)
            deleted += 1
        if deleted == 0:
            # Nothing matched; skip executing pipeline that only had pre-existing commands
            pipe.reset()
        else:
            pipe.execute()
        # Clean up meta/projects set only if all entries for this project were removed
        remaining = r.zcard(self._project_zset(project))
        if remaining == 0:
            r.delete(self._project_zset(project))
            r.delete(self._project_meta(project))
            r.srem(f"{KEY_PREFIX}:projects", project)
        return deleted

    def store_embedding(self, memory_id: int, model_name: str, embedding: list[float]) -> None:
        r = self._client()
        r.set(self._embedding_key(memory_id, model_name), json.dumps(embedding))
        # Track model on memory hash
        r.hset(self._memory_key(memory_id), "embedding_models", model_name)

    def get_embeddings(self, project: str, model_name: str) -> list[tuple[int, list[float]]]:
        r = self._client()
        ids = r.zrange(self._project_zset(project), 0, -1)
        out = []
        for mid in ids:
            emb_raw = r.get(self._embedding_key(int(mid), model_name))
            if emb_raw:
                out.append((int(mid), json.loads(emb_raw)))
        return out

    def list_embedding_models(self, project: str) -> list[str]:
        r = self._client()
        ids = r.zrange(self._project_zset(project), 0, -1)
        models: set[str] = set()
        for mid in ids:
            m = r.hget(self._memory_key(int(mid)), "embedding_models")
            if m:
                models.add(m)
        return sorted(models)

    def list_projects(self, user_id: str | None = None, tenant_id: str | None = None) -> list[str]:
        r = self._client()
        if user_id is None and tenant_id is None:
            return sorted(r.smembers(f"{KEY_PREFIX}:projects"))
        projects: set[str] = set()
        for key in r.scan_iter(match=f"{KEY_PREFIX}:memory:*"):
            data = r.hgetall(key)
            if user_id is not None and data.get("user_id") != user_id:
                continue
            if tenant_id is not None and data.get("tenant_id") != tenant_id:
                continue
            proj = data.get("project")
            if proj:
                projects.add(proj)
        return sorted(projects)

    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        r = self._client()
        return self._load(r, memory_id)

    def update_memory(self, memory_id: int, updates: dict[str, Any]) -> bool:
        r = self._client()
        key = self._memory_key(memory_id)
        if not r.exists(key):
            return False
        allowed = {
            "project",
            "session_id",
            "timestamp",
            "category",
            "content",
            "confidence",
            "source",
            "tags",
            "metadata",
            "user_id",
            "tenant_id",
            "valid_from",
            "valid_until",
        }
        mapping = {}
        for k, v in updates.items():
            if k in allowed:
                mapping[k] = str(v)
        if mapping:
            r.hset(key, mapping=mapping)
        return True

    def delete_memory(self, memory_id: int) -> bool:
        r = self._client()
        key = self._memory_key(memory_id)
        if not r.exists(key):
            return False
        data = r.hgetall(key)
        project = data.get("project", "default")
        pipe = r.pipeline()
        pipe.delete(key)
        pipe.zrem(self._project_zset(project), str(memory_id))
        for emb_key in r.scan_iter(match=f"{KEY_PREFIX}:embedding:{memory_id}:*"):
            pipe.delete(emb_key)
        pipe.execute()
        return True

    def _load(self, r, memory_id: int) -> MemoryEntry | None:
        data = r.hgetall(self._memory_key(memory_id))
        if not data:
            return None
        return self._entry_from_hash(data)

    def _entry_from_hash(self, data: dict[str, str]) -> MemoryEntry | None:
        if not data:
            return None
        return MemoryEntry(
            id=int(data.get("id", 0)),
            project=data.get("project", "default"),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", ""),
            category=data.get("category", "fact"),
            content=data.get("content", ""),
            confidence=float(data.get("confidence", "1.0")),
            source=data.get("source", ""),
            tags=data.get("tags", ""),
            metadata=data.get("metadata", "{}"),
            user_id=data.get("user_id", ""),
            tenant_id=data.get("tenant_id", ""),
            valid_from=data.get("valid_from", ""),
            valid_until=data.get("valid_until", ""),
        )
