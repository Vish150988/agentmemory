"""LLM-powered features: smart summarization, auto-tagging, conflict detection, weekly digest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .core import MemoryEngine
from .llm import LLMClient, get_llm_client
from .semantic import SemanticIndex

SYSTEM_SUMMARIZER = (
    "You are a technical project analyst. Summarize software project "
    "memories into clear, actionable insights. Use bullet points. "
    "Highlight key decisions, risks, and patterns. Be concise."
)

SYSTEM_DIGEST = (
    "You are a developer writing a weekly standup summary. "
    "Summarize what was built, decided, and learned. Use a friendly tone. "
    "Include specific technologies and outcomes."
)


def summarize_project_llm(
    engine: MemoryEngine,
    project: str,
    client: LLMClient | None = None,
) -> str:
    """Generate an LLM-powered project summary.

    Falls back to extractive summarization if no LLM is available.
    """
    client = client or get_llm_client()

    memories = engine.recall(project=project, limit=100)
    if not memories:
        return f"No memories found for project '{project}'."

    if not client.is_available():
        from .summarize import summarize_project

        return summarize_project(engine, project)

    # Build structured input for the LLM
    categories: dict[str, list[str]] = {}
    for m in memories:
        categories.setdefault(m.category, []).append(m.content)

    sections = []
    for cat in ["decision", "action", "error", "preference", "fact"]:
        items = categories.get(cat, [])
        if items:
            lines = "\n".join(f"- {i}" for i in items[:15])
            sections.append(f"## {cat.upper()} ({len(items)})\n{lines}")

    sections_text = "\n\n".join(sections)
    prompt = (
        f"Summarize this software project based on captured memories.\n\n"
        f"Project: {project}\n"
        f"Total memories: {len(memories)}\n\n"
        f"{sections_text}"
    )

    return client.summarize_text(prompt, instruction=SYSTEM_SUMMARIZER)


def summarize_session_llm(
    engine: MemoryEngine,
    session_id: str,
    project: str,
    client: LLMClient | None = None,
) -> str:
    """Generate an LLM-powered session summary."""
    client = client or get_llm_client()

    memories = engine.recall(project=project, session_id=session_id, limit=100)
    if not memories:
        return f"No memories found for session '{session_id}'."

    if not client.is_available():
        from .summarize import summarize_session

        return summarize_session(engine, session_id, project)

    lines = "\n".join(f"[{m.category}] {m.content}" for m in memories)
    prompt = (
        f"Summarize this coding session.\n\nSession: {session_id}\nProject: {project}\n\n{lines}"
    )
    return client.summarize_text(prompt, instruction=SYSTEM_SUMMARIZER)


def generate_weekly_digest(
    engine: MemoryEngine,
    project: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Generate a weekly digest of memories.

    Falls back to a simple list if no LLM is available.
    """
    client = client or get_llm_client()

    # Get memories from the last 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    all_memories = engine.recall(project=project, limit=10000)
    memories = [m for m in all_memories if m.timestamp > cutoff]

    if not memories:
        return "No memories captured in the last 7 days."

    if not client.is_available():
        lines = [f"- [{m.category}] {m.content}" for m in memories[:30]]
        header = f"# Weekly Digest — {project or 'All Projects'}\n\n"
        return header + "\n".join(lines)

    categories: dict[str, list[str]] = {}
    for m in memories:
        categories.setdefault(m.category, []).append(m.content)

    sections = []
    for cat in ["action", "decision", "error", "preference", "fact"]:
        items = categories.get(cat, [])
        if items:
            sections.append(f"## {cat.upper()}\n" + "\n".join(f"- {i}" for i in items[:10]))

    sections_text = "\n\n".join(sections)
    prompt = (
        f"Write a weekly developer digest based on these captured memories.\n\n"
        f"Project: {project or 'Multiple Projects'}\n"
        f"Memories this week: {len(memories)}\n\n"
        f"{sections_text}"
    )

    return client.summarize_text(prompt, instruction=SYSTEM_DIGEST)


def auto_tag_memory(
    content: str,
    client: LLMClient | None = None,
) -> list[str]:
    """Generate smart tags for a memory."""
    client = client or get_llm_client()
    if not client.is_available():
        return []
    return client.generate_tags(content)


def detect_conflicts(
    engine: MemoryEngine,
    project: str,
    threshold: float = 0.3,
    client: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Detect contradictory memories in a project.

    Uses semantic search to find candidate pairs, then LLM to verify.
    Falls back to semantic-only if no LLM.
    """
    client = client or get_llm_client()
    memories = engine.recall(project=project, limit=50)

    if len(memories) < 2:
        return []

    # Strategy: for each high-confidence decision, find semantically similar
    # memories and check for contradictions
    index = SemanticIndex(engine, project, backend="tfidf")
    candidates: list[tuple[int, int]] = []

    for m in memories:
        if m.id is None or m.category != "decision":
            continue
        try:
            results = index.search(m.content, top_k=5, threshold=threshold)
        except Exception:
            continue
        for related, score in results:
            if related.id == m.id:
                continue
            pair = tuple(sorted([m.id, related.id]))  # type: ignore[arg-type]
            if pair not in candidates:
                candidates.append(pair)

    if not candidates:
        return []

    if not client.is_available():
        # Fallback: just flag semantically similar decisions
        return [
            {
                "a": a,
                "b": b,
                "reason": "Semantically similar decisions — may be contradictory.",
            }
            for a, b in candidates[:5]
        ]

    # Build content map
    content_map = {m.id: m.content for m in memories if m.id is not None}
    conflicts: list[dict[str, Any]] = []

    for a, b in candidates[:10]:
        texts = [content_map.get(a, ""), content_map.get(b, "")]
        results = client.detect_contradictions(texts)
        for _, _, reason in results:
            conflicts.append({"a": a, "b": b, "reason": reason})

    return conflicts
