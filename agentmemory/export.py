"""Export memories to various formats."""

from __future__ import annotations

from .core import MemoryEngine

MEMORY_TEMPLATE = """# AgentMemory Export — {project}

## Statistics
- Total memories: {total}
- Sessions: {sessions}

## All Memories

{memories}
"""


def export_markdown(engine: MemoryEngine, project: str) -> str:
    """Export all memories for a project to markdown."""
    memories = engine.recall(project=project, limit=10000)
    stats = engine.stats()

    lines = []
    current_session = ""
    for m in memories:
        if m.session_id != current_session:
            current_session = m.session_id
            lines.append(f"\n### Session: {current_session}\n")
        lines.append(f"- **[{m.category.upper()}]** {m.content}")
        if m.tags:
            lines.append(f"  *Tags: {m.tags}*")
        if m.source:
            lines.append(f"  *Source: {m.source}*")

    return MEMORY_TEMPLATE.format(
        project=project,
        total=len(memories),
        sessions=stats["sessions"],
        memories="\n".join(lines) if lines else "_No memories recorded._",
    )
