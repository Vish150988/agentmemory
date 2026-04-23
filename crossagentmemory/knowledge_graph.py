"""Lightweight knowledge graph built on SQLite.

Extracts entities and relationships from memory content via LLM,
stores them as native graph tables (no Neo4j needed), and enables
traversal queries like "What decisions led to choosing Zustand?"
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import DEFAULT_DB_PATH, MemoryEngine
from .llm import LLMClient, get_llm_client


@dataclass
class GraphNode:
    id: int
    project: str
    name: str
    node_type: str
    created_at: str


@dataclass
class GraphEdge:
    id: int
    project: str
    source_id: int
    target_id: int
    relation: str
    weight: float
    memory_id: int | None
    created_at: str


SYSTEM_KG_EXTRACTOR = (
    "You are a knowledge graph extraction engine. Given a technical memory, "
    "extract entities (technologies, people, concepts, decisions) and the "
    "relationships between them. Output valid JSON only."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _get_db_path(engine: MemoryEngine | None = None) -> Path:
    if engine is not None:
        return engine.db_path
    return DEFAULT_DB_PATH


def _connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_graph_schema(db_path: Path | None = None) -> None:
    """Create graph tables if they don't exist."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connection(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                node_type TEXT NOT NULL DEFAULT 'concept',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_graph_nodes_project ON graph_nodes(project)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_graph_nodes_name ON graph_nodes(name)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL DEFAULT 'default',
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT NOT NULL DEFAULT 'related_to',
                weight REAL NOT NULL DEFAULT 1.0,
                memory_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_graph_edges_project ON graph_edges(project)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_graph_edges_memory ON graph_edges(memory_id)"
        )
        conn.commit()
    finally:
        conn.close()


def extract_entities_and_relations(
    content: str,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Use LLM to extract entities and relations from memory content.

    Returns {"entities": [{"name": str, "type": str}],
             "relations": [{"source": str, "target": str, "relation": str}]}
    """
    client = client or get_llm_client()
    if not client.is_available():
        return {"entities": [], "relations": []}

    prompt = (
        "Extract a knowledge graph from the following technical memory. "
        "Return valid JSON with exactly two keys:\n"
        "- entities: array of {name, type} where type is one of: "
        "technology, person, concept, decision, team, product, library\n"
        "- relations: array of {source, target, relation} where relation is a verb like "
        "uses, replaces, depends_on, led_to, built_with, migrated_from, prefers\n"
        "Only include entities and relations explicitly mentioned or strongly implied.\n\n"
        f"MEMORY:\n{content}"
    )

    resp = client.chat(prompt, system=SYSTEM_KG_EXTRACTOR)
    raw = _sanitize_json(resp.text)

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"entities": [], "relations": []}
        entities = [
            {"name": str(e.get("name", "")), "type": str(e.get("type", "concept"))}
            for e in data.get("entities", [])
            if isinstance(e, dict) and e.get("name")
        ]
        relations = [
            {
                "source": str(r.get("source", "")),
                "target": str(r.get("target", "")),
                "relation": str(r.get("relation", "related_to")),
            }
            for r in data.get("relations", [])
            if isinstance(r, dict) and r.get("source") and r.get("target")
        ]
        return {"entities": entities, "relations": relations}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"entities": [], "relations": []}


def store_extraction(
    project: str,
    memory_id: int,
    extraction: dict[str, Any],
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Store extracted entities and relations into the graph tables.

    Returns {"nodes": int, "edges": int, "node_ids": dict[str, int]}
    """
    path = db_path or DEFAULT_DB_PATH
    init_graph_schema(path)
    conn = _connection(path)
    try:
        node_name_to_id: dict[str, int] = {}
        nodes_created = 0
        edges_created = 0

        # Upsert entities as nodes
        for ent in extraction.get("entities", []):
            name = ent["name"]
            node_type = ent.get("type", "concept")
            # Check if node already exists for this project
            row = conn.execute(
                "SELECT id FROM graph_nodes WHERE project = ? AND name = ?",
                (project, name),
            ).fetchone()
            if row:
                node_name_to_id[name] = row["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO graph_nodes (project, name, node_type, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project, name, node_type, _now_iso()),
                )
                node_name_to_id[name] = cursor.lastrowid  # type: ignore[assignment]
                nodes_created += 1

        # Insert relations as edges
        for rel in extraction.get("relations", []):
            src_name = rel["source"]
            tgt_name = rel["target"]
            relation = rel.get("relation", "related_to")
            src_id = node_name_to_id.get(src_name)
            tgt_id = node_name_to_id.get(tgt_name)
            if src_id is None or tgt_id is None:
                continue
            # Avoid duplicate edges for same memory
            existing = conn.execute(
                """
                SELECT id FROM graph_edges
                WHERE project = ? AND source_id = ? AND target_id = ?
                  AND relation = ? AND memory_id = ?
                """,
                (project, src_id, tgt_id, relation, memory_id),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO graph_edges
                    (project, source_id, target_id, relation, weight, memory_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (project, src_id, tgt_id, relation, 1.0, memory_id, _now_iso()),
                )
                edges_created += 1

        conn.commit()
        return {
            "nodes": nodes_created,
            "edges": edges_created,
            "node_ids": node_name_to_id,
        }
    finally:
        conn.close()


def extract_and_store_for_memory(
    project: str,
    memory_id: int,
    content: str,
    db_path: Path | None = None,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Convenience: extract KG from memory content and store it."""
    extraction = extract_entities_and_relations(content, client=client)
    return store_extraction(project, memory_id, extraction, db_path=db_path)


def get_nodes(
    project: str,
    node_type: str | None = None,
    db_path: Path | None = None,
) -> list[GraphNode]:
    path = db_path or DEFAULT_DB_PATH
    conn = _connection(path)
    try:
        query = "SELECT * FROM graph_nodes WHERE project = ?"
        params: list[Any] = [project]
        if node_type:
            query += " AND node_type = ?"
            params.append(node_type)
        rows = conn.execute(query, params).fetchall()
        return [GraphNode(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_edges(
    project: str,
    relation: str | None = None,
    db_path: Path | None = None,
) -> list[GraphEdge]:
    path = db_path or DEFAULT_DB_PATH
    conn = _connection(path)
    try:
        query = "SELECT * FROM graph_edges WHERE project = ?"
        params: list[Any] = [project]
        if relation:
            query += " AND relation = ?"
            params.append(relation)
        rows = conn.execute(query, params).fetchall()
        return [GraphEdge(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_graph_for_project(
    project: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return the full graph for a project as {nodes, edges}."""
    nodes = get_nodes(project, db_path=db_path)
    edges = get_edges(project, db_path=db_path)
    return {
        "nodes": [
            {"id": n.id, "name": n.name, "type": n.node_type, "created_at": n.created_at}
            for n in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "relation": e.relation,
                "weight": e.weight,
                "memory_id": e.memory_id,
            }
            for e in edges
        ],
    }


def find_paths(
    project: str,
    start_name: str,
    end_name: str,
    max_depth: int = 5,
    db_path: Path | None = None,
) -> list[list[dict[str, Any]]]:
    """Find all paths between two entities up to max_depth.

    Returns list of paths, where each path is a list of edge dicts.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = _connection(path)
    try:
        # Resolve names to IDs
        start_row = conn.execute(
            "SELECT id FROM graph_nodes WHERE project = ? AND name = ?",
            (project, start_name),
        ).fetchone()
        end_row = conn.execute(
            "SELECT id FROM graph_nodes WHERE project = ? AND name = ?",
            (project, end_name),
        ).fetchone()
        if not start_row or not end_row:
            return []

        start_id = start_row["id"]
        end_id = end_row["id"]

        # BFS to find paths
        paths: list[list[dict[str, Any]]] = []
        queue: list[list[int]] = [[start_id]]

        while queue:
            current_path = queue.pop(0)
            current_node = current_path[-1]
            if len(current_path) > max_depth + 1:
                continue
            if current_node == end_id and len(current_path) > 1:
                # Build edge dicts for this path
                edge_path: list[dict[str, Any]] = []
                for i in range(len(current_path) - 1):
                    edge_row = conn.execute(
                        """
                        SELECT * FROM graph_edges
                        WHERE project = ? AND source_id = ? AND target_id = ?
                        """,
                        (project, current_path[i], current_path[i + 1]),
                    ).fetchone()
                    if edge_row:
                        edge_path.append(
                            {
                                "source": current_path[i],
                                "target": current_path[i + 1],
                                "relation": edge_row["relation"],
                                "weight": edge_row["weight"],
                            }
                        )
                paths.append(edge_path)
                continue

            neighbors = conn.execute(
                "SELECT target_id FROM graph_edges WHERE project = ? AND source_id = ?",
                (project, current_node),
            ).fetchall()
            for row in neighbors:
                nxt = row["target_id"]
                if nxt not in current_path:
                    queue.append(current_path + [nxt])

        return paths
    finally:
        conn.close()


def get_related_memories(
    project: str,
    node_name: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Get all memories that contributed edges connected to a given node."""
    path = db_path or DEFAULT_DB_PATH
    conn = _connection(path)
    try:
        node_row = conn.execute(
            "SELECT id FROM graph_nodes WHERE project = ? AND name = ?",
            (project, node_name),
        ).fetchone()
        if not node_row:
            return []
        node_id = node_row["id"]
        rows = conn.execute(
            """
            SELECT DISTINCT m.* FROM memories m
            JOIN graph_edges e ON m.id = e.memory_id
            WHERE e.project = ? AND (e.source_id = ? OR e.target_id = ?)
            ORDER BY m.timestamp DESC
            """,
            (project, node_id, node_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_graph_for_project(project: str, db_path: Path | None = None) -> int:
    """Delete all graph nodes and edges for a project. Returns number of nodes deleted."""
    path = db_path or DEFAULT_DB_PATH
    conn = _connection(path)
    try:
        conn.execute("DELETE FROM graph_edges WHERE project = ?", (project,))
        cursor = conn.execute("DELETE FROM graph_nodes WHERE project = ?", (project,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
