"""REST API server for CrossAgentMemory.

Run with: crossagentmemory server
Requires: pip install fastapi uvicorn

Endpoints:
  GET  /api/memories       - List memories
  GET  /api/memories/{id}  - Get single memory
  POST /api/memories       - Create memory
  PUT  /api/memories/{id}  - Update memory
  DELETE /api/memories/{id} - Delete memory
  GET  /api/search         - Search memories
  GET  /api/projects       - List projects
  GET  /api/stats          - Statistics
  GET  /api/summarize      - LLM-powered summary
  GET  /api/digest         - Weekly digest
  GET  /api/graph          - Memory relationship graph
  GET  /api/conflicts      - Detect contradictions
  POST /api/tag            - Auto-generate tags
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from .core import MemoryEngine, MemoryEntry
from .graph import build_memory_graph, get_category_clusters, get_timeline
from .llm_features import (
    auto_tag_memory,
    detect_conflicts,
    generate_weekly_digest,
    summarize_project_llm,
)

try:
    from fastapi import FastAPI, HTTPException, Query
except ImportError as e:
    raise ImportError("REST API requires fastapi. Install with: pip install fastapi uvicorn") from e

app = FastAPI(title="CrossAgentMemory API", version="0.4.0")


def _engine() -> MemoryEngine:
    return MemoryEngine()


@app.get("/api/memories")
def api_list_memories(
    project: str = "",
    category: str = "",
    session_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    engine = _engine()
    memories = engine.recall(
        project=project or None,
        category=category or None,
        session_id=session_id or None,
        limit=limit,
    )
    return {
        "total": len(memories),
        "offset": offset,
        "memories": [_memory_to_dict(m) for m in memories[offset : offset + limit]],
    }


@app.get("/api/memories/{memory_id}")
def api_get_memory(memory_id: int) -> dict[str, Any]:
    engine = _engine()
    memory = engine.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _memory_to_dict(memory)


@app.post("/api/memories")
def api_create_memory(payload: dict[str, Any]) -> dict[str, Any]:
    engine = _engine()
    entry = MemoryEntry(
        project=payload.get("project", "default"),
        session_id=payload.get(
            "session_id", os.environ.get("CROSSAGENTMEMORY_SESSION", str(uuid.uuid4())[:8])
        ),
        category=payload.get("category", "fact"),
        content=payload["content"],
        confidence=payload.get("confidence", 1.0),
        source=payload.get("source", "api"),
        tags=payload.get("tags", ""),
    )
    memory_id = engine.store(entry)
    return {"id": memory_id, "status": "created"}


@app.put("/api/memories/{memory_id}")
def api_update_memory(memory_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    engine = _engine()
    allowed = {"content", "category", "confidence", "tags"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        return {"id": memory_id, "status": "unchanged"}

    updated = engine.update_memory(memory_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"id": memory_id, "status": "updated"}


@app.delete("/api/memories/{memory_id}")
def api_delete_memory(memory_id: int) -> dict[str, Any]:
    engine = _engine()
    deleted = engine.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"id": memory_id, "status": "deleted"}


@app.get("/api/search")
def api_search(
    q: str = Query(..., description="Search query"),
    project: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    engine = _engine()
    results = engine.search(q, project=project or None, limit=limit)
    return {"query": q, "results": [_memory_to_dict(m) for m in results]}


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    engine = _engine()
    return {"projects": engine.list_projects()}


@app.get("/api/stats")
def api_stats(project: str = "") -> dict[str, Any]:
    engine = _engine()
    data = engine.stats()
    if project:
        data["project_memories"] = len(engine.recall(project=project, limit=10000))
    return data


@app.get("/api/summarize")
def api_summarize(
    project: str = "",
    llm: bool = False,
) -> dict[str, Any]:
    engine = _engine()
    project = project or "default"
    if llm:
        text = summarize_project_llm(engine, project)
    else:
        from .summarize import summarize_project

        text = summarize_project(engine, project)
    return {"project": project, "summary": text}


@app.get("/api/digest")
def api_digest(
    project: str = "",
    days: int = 7,
) -> dict[str, Any]:
    engine = _engine()
    text = generate_weekly_digest(engine, project=project or None)
    return {"project": project or "all", "days": days, "digest": text}


@app.get("/api/graph")
def api_graph(
    project: str = "",
    backend: str = "tfidf",
) -> dict[str, Any]:
    engine = _engine()
    return build_memory_graph(engine, project or "default", backend=backend)


@app.get("/api/timeline")
def api_timeline(
    project: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    engine = _engine()
    return {"timeline": get_timeline(engine, project or "default", limit=limit)}


@app.get("/api/clusters")
def api_clusters(
    project: str = "",
) -> dict[str, Any]:
    engine = _engine()
    return get_category_clusters(engine, project or "default")


@app.get("/api/conflicts")
def api_conflicts(
    project: str = "",
) -> dict[str, Any]:
    engine = _engine()
    project = project or "default"
    conflicts = detect_conflicts(engine, project)
    return {"project": project, "conflicts": conflicts}


@app.post("/api/tag")
def api_tag(payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content", "")
    tags = auto_tag_memory(content)
    return {"content": content, "tags": tags}


def _memory_to_dict(m: MemoryEntry) -> dict[str, Any]:
    return {
        "id": m.id,
        "project": m.project,
        "session_id": m.session_id,
        "timestamp": m.timestamp,
        "category": m.category,
        "content": m.content,
        "confidence": m.confidence,
        "source": m.source,
        "tags": m.tags,
    }


def run_server(host: str = "127.0.0.1", port: int = 8746) -> None:
    """Run the REST API server."""
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError("Server requires uvicorn. Install with: pip install uvicorn") from e

    uvicorn.run(app, host=host, port=port, log_level="warning")
