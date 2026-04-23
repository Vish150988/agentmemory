"""ChromaDB storage backend for CrossAgentMemory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core import DEFAULT_MEMORY_DIR, MemoryEntry
from .base import MemoryBackend


class ChromaBackend(MemoryBackend):
    """ChromaDB-backed memory storage with native vector search."""

    ALLOWED_UPDATE_FIELDS = {
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

    def __init__(self, persist_dir: Path | None = None):
        self.persist_dir = persist_dir or (DEFAULT_MEMORY_DIR / "chroma")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._memories = None
        self._projects = None

    def _get_client(self):
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    def init(self) -> None:
        client = self._get_client()
        self._memories = client.get_or_create_collection("memories")
        self._projects = client.get_or_create_collection("projects")

    def _to_meta(self, entry: MemoryEntry) -> dict[str, Any]:
        return {
            "project": entry.project,
            "session_id": entry.session_id or "",
            "timestamp": entry.timestamp,
            "category": entry.category,
            "source": entry.source or "",
            "tags": entry.tags or "",
            "metadata": entry.metadata or "{}",
            "confidence": float(entry.confidence),
            "user_id": entry.user_id or "",
            "tenant_id": entry.tenant_id or "",
            "valid_from": entry.valid_from or "",
            "valid_until": entry.valid_until or "",
        }

    def _from_doc(self, doc_id: str, document: str, meta: dict[str, Any]) -> MemoryEntry:
        return MemoryEntry(
            id=int(doc_id),
            project=meta.get("project", "default"),
            session_id=meta.get("session_id", ""),
            timestamp=meta.get("timestamp", ""),
            category=meta.get("category", "fact"),
            content=document,
            confidence=float(meta.get("confidence", 1.0)),
            source=meta.get("source", ""),
            tags=meta.get("tags", ""),
            metadata=meta.get("metadata", "{}"),
            user_id=meta.get("user_id", ""),
            tenant_id=meta.get("tenant_id", ""),
            valid_from=meta.get("valid_from", ""),
            valid_until=meta.get("valid_until", ""),
        )

    @staticmethod
    def _valid_at_time(entry: MemoryEntry, at_time: str) -> bool:
        return (not entry.valid_from or entry.valid_from <= at_time) and (
            not entry.valid_until or entry.valid_until >= at_time
        )

    @staticmethod
    def _valid_in_window(
        entry: MemoryEntry,
        window_start: str | None,
        window_end: str | None,
    ) -> bool:
        if window_start is not None:
            if entry.valid_until and entry.valid_until < window_start:
                return False
        if window_end is not None:
            if entry.valid_from and entry.valid_from > window_end:
                return False
        return True

    def store(self, entry: MemoryEntry) -> int:
        import uuid

        # Chroma uses string IDs; use UUID for new entries
        if entry.id is None:
            entry.id = int(uuid.uuid4().int % (10**12))
        doc_id = str(entry.id)
        self._memories.upsert(
            ids=[doc_id],
            documents=[entry.content],
            metadatas=[self._to_meta(entry)],
        )
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
        where: dict[str, Any] = {}
        if project:
            where["project"] = project
        if category:
            where["category"] = category
        if session_id:
            where["session_id"] = session_id
        if user_id:
            where["user_id"] = user_id
        if tenant_id:
            where["tenant_id"] = tenant_id

        if at_time is not None:
            # Fetch without limit so post-query temporal filtering doesn't truncate valid results
            results = self._memories.get(
                where=where if where else None,
            )
            entries = []
            for i, doc_id in enumerate(results["ids"]):
                meta = results["metadatas"][i]
                doc = results["documents"][i]
                entry = self._from_doc(doc_id, doc, meta)
                if self._valid_at_time(entry, at_time):
                    entries.append(entry)
            # Sort by timestamp descending
            entries.sort(key=lambda e: e.timestamp, reverse=True)
            return entries[:limit]

        results = self._memories.get(
            where=where if where else None,
            limit=limit,
        )
        entries = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            doc = results["documents"][i]
            entries.append(self._from_doc(doc_id, doc, meta))
        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries

    def recall_temporal(
        self,
        project: str | None = None,
        at_time: str | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        where: dict[str, Any] = {}
        if project:
            where["project"] = project

        results = self._memories.get(where=where if where else None)
        entries = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            doc = results["documents"][i]
            entry = self._from_doc(doc_id, doc, meta)
            include = True
            if at_time is not None:
                include = include and self._valid_at_time(entry, at_time)
            if window_start is not None or window_end is not None:
                include = include and self._valid_in_window(entry, window_start, window_end)
            if include:
                entries.append(entry)
        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def search(
        self,
        keyword: str,
        project: str | None = None,
        limit: int = 20,
        user_id: str | None = None,
        tenant_id: str | None = None,
        at_time: str | None = None,
    ) -> list[MemoryEntry]:
        where: dict[str, Any] = {}
        if project:
            where["project"] = project
        if user_id:
            where["user_id"] = user_id
        if tenant_id:
            where["tenant_id"] = tenant_id

        if at_time is not None:
            results = self._memories.get(
                where=where if where else None,
                where_document={"$contains": keyword},
            )
            entries = []
            for i, doc_id in enumerate(results["ids"]):
                meta = results["metadatas"][i]
                doc = results["documents"][i]
                entry = self._from_doc(doc_id, doc, meta)
                if self._valid_at_time(entry, at_time):
                    entries.append(entry)
            return entries[:limit]

        results = self._memories.get(
            where=where if where else None,
            where_document={"$contains": keyword},
            limit=limit,
        )
        entries = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            doc = results["documents"][i]
            entries.append(self._from_doc(doc_id, doc, meta))
        return entries

    def get_project_context(self, project: str) -> dict[str, Any]:
        results = self._projects.get(
            ids=[project],
        )
        if not results["ids"]:
            return {}
        meta = results["metadatas"][0]
        try:
            return json.loads(meta.get("context", "{}"))
        except json.JSONDecodeError:
            return {}

    def get_project_description(self, project: str) -> str:
        results = self._projects.get(
            ids=[project],
        )
        if not results["ids"]:
            return ""
        meta = results["metadatas"][0]
        return meta.get("description", "")

    def set_project_context(
        self,
        project: str,
        context: dict[str, Any],
        description: str = "",
    ) -> None:
        self._projects.upsert(
            ids=[project],
            documents=[description or project],
            metadatas=[{"context": json.dumps(context), "description": description}],
        )

    def stats(self, user_id: str | None = None, tenant_id: str | None = None) -> dict[str, Any]:
        if not user_id and not tenant_id:
            count = self._memories.count()
            return {"total_memories": count}

        results = self._memories.get()
        count = 0
        for meta in results["metadatas"]:
            if user_id and meta.get("user_id") != user_id:
                continue
            if tenant_id and meta.get("tenant_id") != tenant_id:
                continue
            count += 1
        return {"total_memories": count}

    def delete_project(
        self, project: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> int:
        results = self._memories.get(where={"project": project})
        ids_to_delete = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            if user_id and meta.get("user_id") != user_id:
                continue
            if tenant_id and meta.get("tenant_id") != tenant_id:
                continue
            ids_to_delete.append(doc_id)
        if ids_to_delete:
            self._memories.delete(ids=ids_to_delete)
        # Only remove project metadata if no memories remain for this project
        remaining = self._memories.get(where={"project": project})
        if not remaining["ids"]:
            self._projects.delete(ids=[project])
        return len(ids_to_delete)

    def store_embedding(self, memory_id: int, model_name: str, embedding: list[float]) -> None:
        doc_id = str(memory_id)
        # Fetch existing to preserve document/metadata
        existing = self._memories.get(ids=[doc_id])
        if not existing["ids"]:
            return
        self._memories.update(
            ids=[doc_id],
            embeddings=[embedding],
        )
        # Track model name in metadata
        meta = existing["metadatas"][0]
        models = set(meta.get("embedding_models", "").split(","))
        models.discard("")
        models.add(model_name)
        meta["embedding_models"] = ",".join(sorted(models))
        self._memories.update(
            ids=[doc_id],
            metadatas=[meta],
        )

    def get_embeddings(self, project: str, model_name: str) -> list[tuple[int, list[float]]]:
        results = self._memories.get(
            where={"project": project},
            include=["embeddings", "metadatas"],
        )
        out = []
        embs = results.get("embeddings")
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            if (
                embs is not None
                and embs[i] is not None
                and model_name in meta.get("embedding_models", "")
            ):
                out.append((int(doc_id), list(embs[i])))
        return out

    def list_embedding_models(self, project: str) -> list[str]:
        results = self._memories.get(where={"project": project})
        models: set[str] = set()
        for meta in results["metadatas"]:
            for m in meta.get("embedding_models", "").split(","):
                if m:
                    models.add(m)
        return sorted(models)

    def list_projects(self, user_id: str | None = None, tenant_id: str | None = None) -> list[str]:
        results = self._memories.get()
        projects: set[str] = set()
        for meta in results["metadatas"]:
            if user_id and meta.get("user_id") != user_id:
                continue
            if tenant_id and meta.get("tenant_id") != tenant_id:
                continue
            projects.add(meta.get("project", "default"))
        return sorted(projects)

    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        doc_id = str(memory_id)
        results = self._memories.get(ids=[doc_id])
        if not results["ids"]:
            return None
        return self._from_doc(results["ids"][0], results["documents"][0], results["metadatas"][0])

    def update_memory(self, memory_id: int, updates: dict[str, Any]) -> bool:
        entry = self.get_memory_by_id(memory_id)
        if entry is None:
            return False
        for key, value in updates.items():
            if key in self.ALLOWED_UPDATE_FIELDS:
                setattr(entry, key, value)
        doc_id = str(memory_id)
        self._memories.update(
            ids=[doc_id],
            documents=[entry.content],
            metadatas=[self._to_meta(entry)],
        )
        return True

    def delete_memory(self, memory_id: int) -> bool:
        doc_id = str(memory_id)
        existing = self._memories.get(ids=[doc_id])
        if not existing["ids"]:
            return False
        self._memories.delete(ids=[doc_id])
        return True
