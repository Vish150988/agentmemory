"""ChromaDB storage backend for CrossAgentMemory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core import DEFAULT_MEMORY_DIR, MemoryEntry
from .base import MemoryBackend


class ChromaBackend(MemoryBackend):
    """ChromaDB-backed memory storage with native vector search."""

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
        )

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
    ) -> list[MemoryEntry]:
        where: dict[str, Any] = {}
        if project:
            where["project"] = project
        if category:
            where["category"] = category
        if session_id:
            where["session_id"] = session_id

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

    def search(
        self,
        keyword: str,
        project: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        where: dict[str, Any] = {}
        if project:
            where["project"] = project

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

    def stats(self) -> dict[str, Any]:
        count = self._memories.count()
        return {"total_memories": count}

    def delete_project(self, project: str) -> int:
        results = self._memories.get(where={"project": project})
        ids = results["ids"]
        if ids:
            self._memories.delete(ids=ids)
        self._projects.delete(ids=[project])
        return len(ids)

    def store_embedding(
        self, memory_id: int, model_name: str, embedding: list[float]
    ) -> None:
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

    def get_embeddings(
        self, project: str, model_name: str
    ) -> list[tuple[int, list[float]]]:
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

    def list_projects(self) -> list[str]:
        # Chroma doesn't support distinct queries; scan all metadata
        results = self._memories.get()
        projects: set[str] = set()
        for meta in results["metadatas"]:
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
            if hasattr(entry, key):
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
