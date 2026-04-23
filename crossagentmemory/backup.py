"""Backup and restore for CrossAgentMemory.

Formats:
  - .zip  (default): memories.json + projects.json + embeddings.json + meta.json
  - .json (single file): all data in one JSON document
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import MemoryEngine, MemoryEntry


def create_backup(
    engine: MemoryEngine,
    output_path: Path,
    project: str | None = None,
) -> dict[str, Any]:
    """Create a backup of all memories, projects, and embeddings.

    Returns metadata about the backup.
    """
    output_path = Path(output_path)

    # Collect memories
    memories = engine.recall(project=project, limit=1_000_000)
    memory_list = [
        {
            "id": m.id,
            "project": m.project,
            "session_id": m.session_id,
            "timestamp": m.timestamp,
            "category": m.category,
            "content": m.content,
            "confidence": m.confidence,
            "source": m.source,
            "tags": m.tags,
            "metadata": m.metadata,
        }
        for m in memories
    ]

    # Collect projects
    projects = []
    for proj in engine.list_projects():
        if project and proj != project:
            continue
        ctx = engine.get_project_context(proj)
        desc = engine.get_project_description(proj)
        projects.append(
            {
                "name": proj,
                "description": desc,
                "context": ctx,
            }
        )

    # Collect embeddings
    embeddings = []
    for proj in engine.list_projects():
        if project and proj != project:
            continue
        for model_name in engine.list_embedding_models(proj):
            for memory_id, emb in engine.get_embeddings(proj, model_name):
                embeddings.append(
                    {
                        "memory_id": memory_id,
                        "project": proj,
                        "model_name": model_name,
                        "embedding": emb,
                    }
                )

    meta = {
        "version": "1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_filter": project,
        "memory_count": len(memory_list),
        "project_count": len(projects),
        "embedding_count": len(embeddings),
    }

    if output_path.suffix.lower() == ".json":
        payload = {
            "meta": meta,
            "memories": memory_list,
            "projects": projects,
            "embeddings": embeddings,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        # Default to zip
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", json.dumps(meta, indent=2))
            zf.writestr("memories.json", json.dumps(memory_list, indent=2))
            zf.writestr("projects.json", json.dumps(projects, indent=2))
            zf.writestr("embeddings.json", json.dumps(embeddings, indent=2))

    return {
        "path": str(output_path),
        "memories": len(memory_list),
        "projects": len(projects),
        "embeddings": len(embeddings),
    }


def restore_backup(
    engine: MemoryEngine,
    input_path: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore memories, projects, and embeddings from a backup.

    Returns counts of what was imported.
    """
    input_path = Path(input_path)

    if input_path.suffix.lower() == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        _ = payload.get("meta", {})
        memory_list = payload.get("memories", [])
        project_list = payload.get("projects", [])
        embedding_list = payload.get("embeddings", [])
    else:
        with zipfile.ZipFile(input_path, "r") as zf:
            _ = json.loads(zf.read("meta.json"))
            memory_list = json.loads(zf.read("memories.json"))
            project_list = json.loads(zf.read("projects.json"))
            embedding_list = json.loads(zf.read("embeddings.json"))

    if dry_run:
        return {
            "dry_run": True,
            "memories": len(memory_list),
            "projects": len(project_list),
            "embeddings": len(embedding_list),
        }

    # Restore projects first (so contexts exist)
    for p in project_list:
        engine.set_project_context(
            p["name"],
            p.get("context", {}),
            description=p.get("description", ""),
        )

    # Restore memories (map old IDs to new IDs)
    id_map: dict[int, int] = {}
    for m in memory_list:
        old_id = m["id"]
        entry = MemoryEntry(
            project=m["project"],
            session_id=m["session_id"],
            timestamp=m["timestamp"],
            category=m["category"],
            content=m["content"],
            confidence=m["confidence"],
            source=m["source"],
            tags=m["tags"],
            metadata=m.get("metadata", "{}"),
        )
        new_id = engine.store(entry)
        if old_id is not None:
            id_map[old_id] = new_id

    # Restore embeddings using ID map
    restored_embeddings = 0
    for e in embedding_list:
        old_memory_id = e["memory_id"]
        new_memory_id = id_map.get(old_memory_id)
        if new_memory_id:
            engine.store_embedding(new_memory_id, e["model_name"], e["embedding"])
            restored_embeddings += 1

    return {
        "memories": len(memory_list),
        "projects": len(project_list),
        "embeddings": restored_embeddings,
    }
