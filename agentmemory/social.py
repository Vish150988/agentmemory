"""Social media integration — auto-share milestones via agent-reach.

Requires: agent-reach skill installed and configured.
Posts updates when significant events happen (team sync, major captures, etc.).
"""

from __future__ import annotations

import subprocess

from .core import MemoryEngine


def _has_agent_reach() -> bool:
    """Check if agent-reach CLI is available."""
    try:
        result = subprocess.run(
            ["agent-reach", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _post_to_twitter(message: str) -> bool:
    """Post a message to Twitter/X via agent-reach."""
    if not _has_agent_reach():
        return False
    try:
        result = subprocess.run(
            ["agent-reach", "twitter", "post", message],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _post_to_linkedin(message: str) -> bool:
    """Post a message to LinkedIn via agent-reach."""
    if not _has_agent_reach():
        return False
    try:
        result = subprocess.run(
            ["agent-reach", "linkedin", "post", message],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def post_milestone(
    project: str,
    milestone: str,
    platforms: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, bool]:
    """Post a project milestone to social media.

    Args:
        project: Project name
        milestone: Description of the milestone
        platforms: List of platforms (twitter, linkedin). Defaults to both.
        dry_run: If True, only print what would be posted

    Returns:
        Dict of platform -> success
    """
    platforms = platforms or ["twitter", "linkedin"]
    engine = MemoryEngine()
    stats = engine.stats()

    message = (
        f"Building {project}: {milestone}\n\n"
        f"AgentMemory now holds {stats['total_memories']} memories "
        f"across {stats['projects']} projects. "
        f"Cross-agent memory layer for AI coding agents.\n\n"
        f"github.com/Vish150988/agentmemory"
    )

    if dry_run:
        print(f"[DRY RUN] Would post to {', '.join(platforms)}:")
        print(message)
        return {p: False for p in platforms}

    results: dict[str, bool] = {}
    for platform in platforms:
        if platform == "twitter":
            results[platform] = _post_to_twitter(message)
        elif platform == "linkedin":
            results[platform] = _post_to_linkedin(message)
        else:
            results[platform] = False

    return results


def post_project_summary(project: str, platforms: list[str] | None = None) -> dict[str, bool]:
    """Generate and post a project summary."""
    from .summarize import summarize_project

    engine = MemoryEngine()
    summary = summarize_project(engine, project)

    # Extract first few lines as the milestone
    lines = [line.strip("- ") for line in summary.splitlines() if line.strip().startswith("-")]
    milestone = lines[0] if lines else f"Project {project} update"

    return post_milestone(project, milestone, platforms)


def auto_post_on_sync(project: str, platforms: list[str] | None = None) -> dict[str, bool]:
    """Auto-post when team sync exports a significant number of memories."""
    engine = MemoryEngine()
    count = len(engine.recall(project=project, limit=10000))

    if count < 10:
        return {}  # Too few memories to post about

    milestone = f"Team sync: {count} memories shared for {project}"
    return post_milestone(project, milestone, platforms)
