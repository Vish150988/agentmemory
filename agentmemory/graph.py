"""Memory graph — build relationship networks between memories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import MemoryEngine
from .semantic import SemanticIndex


@dataclass
class MemoryNode:
    id: int
    content: str
    category: str
    confidence: float


@dataclass
class MemoryEdge:
    source: int
    target: int
    weight: float


def build_memory_graph(
    engine: MemoryEngine,
    project: str,
    backend: str = "tfidf",
    threshold: float = 0.15,
    max_nodes: int = 50,
) -> dict[str, Any]:
    """Build a relationship graph for memories in a project.

    Uses semantic search to find related memories and creates edges
    between them based on similarity scores.

    Returns:
        dict with 'nodes' and 'edges' for visualization.
    """
    memories = engine.recall(project=project, limit=max_nodes)
    if not memories:
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, Any]] = []
    node_ids: set[int] = set()
    edges: list[dict[str, Any]] = []

    for m in memories:
        if m.id is not None:
            nodes.append(
                {
                    "id": m.id,
                    "content": m.content[:80] + "..." if len(m.content) > 80 else m.content,
                    "category": m.category,
                    "confidence": m.confidence,
                }
            )
            node_ids.add(m.id)

    # Build edges using semantic similarity
    index = SemanticIndex(engine, project, backend=backend)

    for m in memories:
        if m.id is None:
            continue
        try:
            results = index.search(m.content, top_k=5, threshold=threshold)
        except Exception:
            continue

        for related, score in results:
            if related.id == m.id:
                continue
            if related.id not in node_ids:
                continue
            # Only add edge once (source < target to avoid duplicates)
            if m.id < related.id:
                edges.append(
                    {
                        "source": m.id,
                        "target": related.id,
                        "weight": round(score, 3),
                    }
                )

    return {"nodes": nodes, "edges": edges}


def get_category_clusters(
    engine: MemoryEngine,
    project: str,
) -> dict[str, list[dict[str, Any]]]:
    """Group memories by category for cluster visualization."""
    categories = ["fact", "decision", "action", "preference", "error"]
    clusters: dict[str, list[dict[str, Any]]] = {}

    for cat in categories:
        memories = engine.recall(project=project, category=cat, limit=20)
        clusters[cat] = [
            {
                "id": m.id,
                "content": m.content[:60] + "..." if len(m.content) > 60 else m.content,
                "confidence": m.confidence,
            }
            for m in memories
            if m.id is not None
        ]

    return clusters


def get_timeline(
    engine: MemoryEngine,
    project: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Get memories in timeline format for visualization."""
    memories = engine.recall(project=project, limit=limit)
    return [
        {
            "id": m.id,
            "content": m.content[:60] + "..." if len(m.content) > 60 else m.content,
            "category": m.category,
            "timestamp": m.timestamp,
            "confidence": m.confidence,
        }
        for m in memories
        if m.id is not None
    ]
