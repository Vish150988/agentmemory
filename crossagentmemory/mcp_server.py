"""MCP (Model Context Protocol) server for CrossAgentMemory.

Exposes CrossAgentMemory as tools that any MCP-compatible agent can call.
Requires: pip install fastmcp
"""

from __future__ import annotations

import json
from typing import Any

from .core import MemoryEngine, MemoryEntry
from .semantic import SemanticIndex
from .summarize import summarize_project, summarize_session

try:
    from fastmcp import FastMCP
except ImportError as e:
    raise ImportError("MCP server requires fastmcp. Install with: pip install fastmcp") from e

mcp = FastMCP(
    "crossagentmemory",
    instructions=(
        "crossagentmemory mcp server — tools for persistent cross-agent memory. "
        "Use memory_recall to get context, memory_search to find specifics, "
        "memory_capture to store decisions, and memory_summarize for overviews."
    ),
)


@mcp.tool()
def memory_recall(project: str, category: str = "", limit: int = 20) -> str:
    """Recall recent memories for a project.

    Args:
        project: Project name to query.
        category: Optional filter (fact, decision, action, preference, error).
        limit: Maximum number of memories to return.

    Returns:
        JSON string with list of memories.
    """
    engine = MemoryEngine()
    memories = engine.recall(
        project=project,
        category=category or None,
        limit=limit,
    )
    data = [
        {
            "id": m.id,
            "content": m.content,
            "category": m.category,
            "confidence": m.confidence,
            "source": m.source,
            "tags": m.tags,
            "timestamp": m.timestamp,
        }
        for m in memories
    ]
    return json.dumps({"project": project, "memories": data}, indent=2)


@mcp.tool()
def memory_search(project: str, keyword: str, limit: int = 10) -> str:
    """Search memories by keyword.

    Args:
        project: Project name to query.
        keyword: Search term.
        limit: Maximum results.

    Returns:
        JSON string with matching memories.
    """
    engine = MemoryEngine()
    results = engine.search(keyword, project=project, limit=limit)
    data = [
        {
            "id": m.id,
            "content": m.content,
            "category": m.category,
            "confidence": m.confidence,
            "source": m.source,
            "timestamp": m.timestamp,
        }
        for m in results
    ]
    return json.dumps({"project": project, "keyword": keyword, "results": data}, indent=2)


@mcp.tool()
def memory_capture(
    project: str,
    content: str,
    category: str = "fact",
    confidence: float = 1.0,
    tags: str = "",
    source: str = "mcp",
) -> str:
    """Capture a new memory.

    Args:
        project: Project name.
        content: Memory content.
        category: fact, decision, action, preference, or error.
        confidence: 0.0 to 1.0.
        tags: Comma-separated tags.
        source: Source identifier (e.g., 'claude', 'cursor').

    Returns:
        JSON with the new memory ID.
    """
    engine = MemoryEngine()
    import os
    import uuid

    session_id = os.environ.get("CROSSAGENTMEMORY_SESSION", str(uuid.uuid4())[:8])
    entry = MemoryEntry(
        project=project,
        session_id=session_id,
        category=category,
        content=content,
        confidence=confidence,
        source=source,
        tags=tags,
    )
    memory_id = engine.store(entry)
    return json.dumps(
        {"status": "stored", "memory_id": memory_id, "project": project},
        indent=2,
    )


@mcp.tool()
def memory_summarize(project: str, session: str = "") -> str:
    """Summarize a project or specific session.

    Args:
        project: Project name.
        session: Optional session ID. If empty, summarizes entire project.

    Returns:
        Markdown summary string.
    """
    engine = MemoryEngine()
    if session:
        text = summarize_session(engine, session, project)
    else:
        text = summarize_project(engine, project)
    return text


@mcp.tool()
def memory_stats(project: str = "") -> str:
    """Get memory statistics.

    Args:
        project: Optional project name. If empty, returns global stats.

    Returns:
        JSON with statistics.
    """
    engine = MemoryEngine()
    data: dict[str, Any] = engine.stats()
    if project:
        project_memories = engine.recall(project=project, limit=10000)
        data["project"] = project
        data["project_memories"] = len(project_memories)
    return json.dumps(data, indent=2)


@mcp.tool()
def memory_related(project: str, query: str, top_k: int = 5, backend: str = "auto") -> str:
    """Find semantically related memories.

    Args:
        project: Project name.
        query: Query text.
        top_k: Number of results.
        backend: 'auto', 'tfidf', or 'sentence-transformers'.

    Returns:
        JSON with related memories and similarity scores.
    """
    engine = MemoryEngine()
    index = SemanticIndex(engine, project, backend=backend)
    results = index.search(query, top_k=top_k)
    data = [
        {
            "id": m.id,
            "content": m.content,
            "category": m.category,
            "similarity": round(score, 3),
        }
        for m, score in results
    ]
    return json.dumps({"project": project, "query": query, "results": data}, indent=2)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")
