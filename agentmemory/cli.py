"""CLI interface for AgentMemory."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .core import DEFAULT_MEMORY_DIR, MemoryEngine, MemoryEntry
from .decay import decay_confidence, reinforce_memory
from .export import export_markdown
from .hooks import install_hooks, uninstall_hooks
from .recall import build_context_brief
from .semantic import SemanticIndex
from .summarize import summarize_project, summarize_session

console = Console()


def _get_project() -> str:
    """Detect project name from git repo or directory name."""
    cwd = Path.cwd()
    git_dir = cwd / ".git"
    if git_dir.exists():
        # Try to read git config for remote name
        try:
            import subprocess

            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Extract repo name from URL
                name = url.split("/")[-1].replace(".git", "")
                if name:
                    return name
        except Exception:
            pass
    return cwd.name


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """AgentMemory — Cross-agent memory layer for AI coding agents."""
    pass


@main.command()
@click.option("--project", "-p", help="Project name (auto-detected by default)")
def init(project: str | None) -> None:
    """Initialize agent memory for the current project."""
    project = project or _get_project()
    engine = MemoryEngine()

    # Store minimal project context
    engine.set_project_context(
        project,
        context={
            "initialized_at": str(Path.cwd()),
            "cwd": str(Path.cwd()),
        },
        description=f"Project initialized at {Path.cwd()}",
    )

    console.print(
        f"[green][OK][/green] Initialized agent memory for project: [bold]{project}[/bold]"
    )
    console.print(f"  Database: {DEFAULT_MEMORY_DIR / 'memory.db'}")


@main.command()
@click.argument("content")
@click.option("--project", "-p", help="Project name")
@click.option(
    "--category",
    "-c",
    default="fact",
    type=click.Choice(["fact", "decision", "action", "preference", "error"]),
)
@click.option("--confidence", default=1.0, type=float)
@click.option("--tags", "-t", default="", help="Comma-separated tags")
@click.option("--source", "-s", default="user", help="Source of the memory")
def capture(
    content: str,
    project: str | None,
    category: str,
    confidence: float,
    tags: str,
    source: str,
) -> None:
    """Capture a memory entry."""
    project = project or _get_project()
    engine = MemoryEngine()

    session_id = os.environ.get("AGENTMEMORY_SESSION", str(uuid.uuid4())[:8])

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
    console.print(
        f"[green][OK][/green] Captured memory [bold]#{memory_id}[/bold] in [bold]{project}[/bold]"
    )


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--category", "-c", help="Filter by category")
@click.option("--limit", "-n", default=20, help="Number of memories to show")
def recall(project: str | None, category: str | None, limit: int) -> None:
    """Recall recent memories."""
    project = project or _get_project()
    engine = MemoryEngine()
    memories = engine.recall(project=project, category=category, limit=limit)

    if not memories:
        console.print(f"[yellow]No memories found for project '{project}'[/yellow]")
        return

    table = Table(title=f"Recent Memories — {project}")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Category", width=12)
    table.add_column("Content")
    table.add_column("Source", width=12)
    table.add_column("Time", width=16)

    for m in memories:
        table.add_row(
            str(m.id),
            f"[bold]{m.category}[/bold]",
            m.content[:80] + ("..." if len(m.content) > 80 else ""),
            m.source,
            m.timestamp[:16].replace("T", " "),
        )

    console.print(table)


@main.command()
@click.argument("keyword")
@click.option("--project", "-p", help="Project name")
@click.option("--limit", "-n", default=10)
def search(keyword: str, project: str | None, limit: int) -> None:
    """Search memories by keyword."""
    project = project or _get_project()
    engine = MemoryEngine()
    results = engine.search(keyword, project=project, limit=limit)

    if not results:
        console.print(f"[yellow]No results for '{keyword}'[/yellow]")
        return

    for m in results:
        console.print(f"[bold]#{m.id}[/bold] [{m.category}] {m.content[:100]}")


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def load(project: str | None, output: str | None) -> None:
    """Load context briefing for your AI agent."""
    project = project or _get_project()
    engine = MemoryEngine()
    brief = build_context_brief(engine, project)

    if output:
        Path(output).write_text(brief, encoding="utf-8")
        console.print(f"[green][OK][/green] Context written to {output}")
    else:
        console.print("\n[bold cyan]--- Agent Context Brief ---[/bold cyan]\n")
        console.print(brief)
        console.print("\n[dim]Copy the above into your agent's context.[/dim]")


@main.command()
@click.option("--project", "-p", help="Project name")
def sync(project: str | None) -> None:
    """Sync memory to CLAUDE.md in the current project."""
    from .sync import sync_project

    path = sync_project(project)
    console.print(f"[green][OK][/green] Synced memory to [bold]{path}[/bold]")


@main.group()
def hook() -> None:
    """Manage git hooks for AgentMemory."""
    pass


@hook.command("install")
def hook_install() -> None:
    """Install git hooks to auto-sync CLAUDE.md on commits."""
    try:
        pre, post = install_hooks()
        console.print("[green][OK][/green] Installed git hooks:")
        console.print(f"  - {pre.name}")
        console.print(f"  - {post.name}")
        console.print("\n[dim]CLAUDE.md will auto-sync before and after each commit.[/dim]")
    except RuntimeError as e:
        console.print(f"[red][ERROR][/red] {e}")


@hook.command("uninstall")
def hook_uninstall() -> None:
    """Remove AgentMemory git hooks."""
    uninstall_hooks()
    console.print("[green][OK][/green] Removed AgentMemory git hooks.")


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--output", "-o", type=click.Path(), help="Output markdown file")
def export(project: str | None, output: str | None) -> None:
    """Export memories to markdown."""
    project = project or _get_project()
    engine = MemoryEngine()
    md = export_markdown(engine, project)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"[green][OK][/green] Exported to {output}")
    else:
        out_path = Path.cwd() / f"AGENT_MEMORY_{project}.md"
        out_path.write_text(md, encoding="utf-8")
        console.print(f"[green][OK][/green] Exported to {out_path}")


@main.command()
def stats() -> None:
    """Show memory statistics."""
    engine = MemoryEngine()
    data = engine.stats()

    console.print("[bold]AgentMemory Stats[/bold]\n")
    console.print(f"Total memories: {data['total_memories']}")
    console.print(f"Projects: {data['projects']}")
    console.print(f"Sessions: {data['sessions']}")
    if data["by_category"]:
        console.print("\nBy category:")
        for cat, count in data["by_category"].items():
            console.print(f"  {cat}: {count}")


@main.command()
@click.argument("project")
@click.confirmation_option(prompt="Are you sure you want to delete all memories for this project?")
def delete(project: str) -> None:
    """Delete all memories for a project."""
    engine = MemoryEngine()
    count = engine.delete_project(project)
    console.print(f"[red][DELETED][/red] {count} memories for project '{project}'")


@main.command()
@click.argument("query")
@click.option("--project", "-p", help="Project name")
@click.option("--limit", "-n", default=10, help="Number of results")
def related(query: str, project: str | None, limit: int) -> None:
    """Find memories semantically related to a query."""
    project = project or _get_project()
    engine = MemoryEngine()
    index = SemanticIndex(engine, project)
    results = index.search(query, top_k=limit)

    if not results:
        console.print(f"[yellow]No related memories found for '{query}'[/yellow]")
        return

    table = Table(title=f"Related to: {query}")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Similarity", width=10)
    table.add_column("Category", width=12)
    table.add_column("Content")

    for memory, score in results:
        table.add_row(
            str(memory.id),
            f"{score:.2f}",
            memory.category,
            memory.content[:70] + ("..." if len(memory.content) > 70 else ""),
        )

    console.print(table)


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--session", "-s", help="Session ID to summarize")
@click.option("--output", "-o", type=click.Path(), help="Output file")
def summarize(project: str | None, session: str | None, output: str | None) -> None:
    """Summarize memories (session or entire project)."""
    project = project or _get_project()
    engine = MemoryEngine()

    if session:
        text = summarize_session(engine, session, project)
        title = f"Session: {session}"
    else:
        text = summarize_project(engine, project)
        title = f"Project: {project}"

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green][OK][/green] Summary written to {output}")
    else:
        console.print(f"\n[bold cyan]--- {title} ---[/bold cyan]\n")
        console.print(text)


@main.command()
@click.argument("memory_id", type=int)
@click.option("--boost", default=0.1, type=float, help="Confidence boost amount")
def reinforce(memory_id: int, boost: float) -> None:
    """Reinforce a memory (boost confidence)."""
    engine = MemoryEngine()
    if reinforce_memory(engine, memory_id, boost):
        console.print(f"[green][OK][/green] Reinforced memory #{memory_id}")
    else:
        console.print(f"[red][ERROR][/red] Memory #{memory_id} not found")


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--half-life", default=30.0, help="Days for confidence to halve")
@click.option("--dry-run", is_flag=True, help="Show what would change without updating")
def decay(project: str | None, half_life: float, dry_run: bool) -> None:
    """Decay old memory confidence."""
    engine = MemoryEngine()
    stats = decay_confidence(engine, project=project, half_life_days=half_life, dry_run=dry_run)

    mode = "[DRY RUN] " if dry_run else ""
    console.print(f"{mode}Memory decay complete:")
    console.print(f"  Processed: {stats['total_processed']}")
    console.print(f"  Updated: {stats['updated']}")
    console.print(f"  Unchanged: {stats['unchanged']}")
    console.print(f"  Archived (confidence < 0.1): {stats['archived']}")


if __name__ == "__main__":
    main()
