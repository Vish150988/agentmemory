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
from .graph import build_memory_graph
from .hooks import install_hooks, uninstall_hooks
from .recall import build_context_brief
from .semantic import SemanticIndex
from .shell import _get_shell_config_path, generate_shell_integration
from .summarize import summarize_project, summarize_session
from .team_sync import team_export, team_import, team_status

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
@click.version_option(version="0.3.0")
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


@main.group()
def team() -> None:
    """Team sync — share memories via git."""
    pass


@team.command("export")
@click.option("--project", "-p", help="Project name")
@click.option("--cwd", type=click.Path(), default=".", help="Project directory")
def team_export_cmd(project: str | None, cwd: str) -> None:
    """Export memories to .agent-memory/ for team sharing."""
    project = project or _get_project()
    path = team_export(project, cwd=Path(cwd))
    console.print(f"[green][OK][/green] Exported team memory to [bold]{path}[/bold]")
    console.print("[dim]Commit the .agent-memory/ folder to share with your team.[/dim]")


@team.command("import")
@click.option("--project", "-p", help="Project name")
@click.option("--cwd", type=click.Path(), default=".", help="Project directory")
@click.option("--dry-run", is_flag=True, help="Preview without importing")
def team_import_cmd(project: str | None, cwd: str, dry_run: bool) -> None:
    """Import team-shared memories from .agent-memory/."""
    project = project or _get_project()
    stats = team_import(project, cwd=Path(cwd), dry_run=dry_run)
    mode = "[DRY RUN] " if dry_run else ""
    console.print(f"{mode}[green][OK][/green] Team sync complete for [bold]{project}[/bold]")
    console.print(f"  Files scanned: {stats['files']}")
    console.print(f"  Imported: {stats['imported']}")
    console.print(f"  Skipped (duplicates): {stats['skipped']}")


@team.command("status")
@click.option("--project", "-p", help="Project name")
@click.option("--cwd", type=click.Path(), default=".", help="Project directory")
def team_status_cmd(project: str | None, cwd: str) -> None:
    """Show team sync status."""
    project = project or _get_project()
    info = team_status(project, cwd=Path(cwd))
    console.print(f"[bold]Team Sync — {project}[/bold]\n")
    console.print(f"Local memories: {info['local_memories']}")
    console.print(f"Team folder: {info['team_folder']}")
    console.print(f"Team folder exists: {'yes' if info['team_folder_exists'] else 'no'}")
    console.print(f"Export files: {info['export_files']}")
    if info['latest_export']:
        console.print(f"Latest export: {info['latest_export']}")


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option(
    "--sources",
    "-s",
    default="shell,git,claude",
    help="Comma-separated sources: shell, git, claude",
)
@click.option("--dry-run", is_flag=True, help="Preview without storing")
def capture_auto(project: str | None, sources: str, dry_run: bool) -> None:
    """Auto-capture memories from shell history, git log, and Claude sessions."""
    from .auto_capture import (
        auto_capture_all,
        capture_from_claude_logs,
        capture_from_git_log,
        capture_from_shell_history,
    )

    project = project or _get_project()
    source_list = [s.strip() for s in sources.split(",")]

    if dry_run:
        entries: list = []
        if "shell" in source_list:
            entries.extend(capture_from_shell_history(project))
        if "git" in source_list:
            entries.extend(capture_from_git_log(project))
        if "claude" in source_list:
            entries.extend(capture_from_claude_logs(project))
        console.print(f"[bold]Dry run — would capture {len(entries)} memories:[/bold]\n")
        for e in entries[:10]:
            console.print(f"  [{e.category}] {e.content[:80]}...")
        if len(entries) > 10:
            console.print(f"  ... and {len(entries) - 10} more")
        return

    counts = auto_capture_all(project, sources=source_list)
    total = sum(counts.values())
    console.print(f"[green][OK][/green] Auto-captured [bold]{total}[/bold] memories:")
    for src, count in counts.items():
        console.print(f"  {src}: {count}")


@main.command()
def mcp() -> None:
    """Start the AgentMemory MCP server (stdio)."""
    try:
        from .mcp_server import main as mcp_main
    except ImportError as e:
        console.print(f"[red][ERROR][/red] {e}")
        console.print("[dim]Install with: pip install fastmcp[/dim]")
        raise click.Exit(1)
    mcp_main()


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8745, help="Port to bind")
def dashboard(host: str, port: int) -> None:
    """Start the AgentMemory web dashboard."""
    try:
        from .dashboard import run_dashboard
    except ImportError as e:
        console.print(f"[red][ERROR][/red] {e}")
        console.print("[dim]Install with: pip install fastapi uvicorn[/dim]")
        raise click.Exit(1)
    console.print(f"[green][OK][/green] Starting dashboard at http://{host}:{port}")
    run_dashboard(host=host, port=port)


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
@click.option(
    "--backend",
    "-b",
    default="auto",
    type=click.Choice(["auto", "tfidf", "sentence-transformers"]),
    help="Semantic search backend",
)
def related(query: str, project: str | None, limit: int, backend: str) -> None:
    """Find memories semantically related to a query."""
    project = project or _get_project()
    engine = MemoryEngine()
    index = SemanticIndex(engine, project, backend=backend)
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


@main.group()
def shell() -> None:
    """Shell integration — auto-inject context into agents."""
    pass


@shell.command("show")
@click.option("--shell", "-s", default="auto", help="Shell type (bash, zsh, fish, powershell)")
def shell_show(shell: str) -> None:
    """Show shell integration script."""
    from .shell import detect_shell

    detected = detect_shell() if shell == "auto" else shell
    script = generate_shell_integration(detected)
    config_path = _get_shell_config_path(detected)
    console.print(f"[bold]Shell integration for {detected}[/bold]")
    console.print(f"[dim]Add to: {config_path}[/dim]\n")
    console.print(script)


@main.group()
def daemon() -> None:
    """Background daemon for silent auto-capture."""
    pass


@daemon.command("start")
@click.option("--project", "-p", help="Project name")
@click.option("--interval", default=60.0, help="Polling interval in seconds")
def daemon_start(project: str | None, interval: float) -> None:
    """Start the background daemon."""
    from .daemon import daemon_status, start_daemon

    project = project or _get_project()
    start_daemon(project, interval=interval)
    status = daemon_status()
    console.print(f"[green][OK][/green] Daemon started for [bold]{status['project']}[/bold]")
    console.print(f"  Watch dir: {status['watch_dir']}")
    console.print(f"  Interval: {status['interval']}s")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    try:
        import time

        while status["running"]:
            time.sleep(1)
            status = daemon_status()
    except KeyboardInterrupt:
        from .daemon import stop_daemon

        stop_daemon()
        console.print("[green][OK][/green] Daemon stopped.")


@daemon.command("status")
def daemon_status_cmd() -> None:
    """Show daemon status."""
    from .daemon import daemon_status

    status = daemon_status()
    if status["running"]:
        console.print("[green]Daemon is running[/green]")
        console.print(f"  Project: {status['project']}")
        console.print(f"  Watch dir: {status['watch_dir']}")
        console.print(f"  Interval: {status['interval']}s")
    else:
        console.print("[yellow]Daemon is not running[/yellow]")


@main.command()
@click.argument("source_path", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "fmt",
    default="auto",
    type=click.Choice(["auto", "mem0", "markdown", "json"]),
)
@click.option("--project", "-p", help="Target project name")
def import_(source_path: str, fmt: str, project: str | None) -> None:
    """Import memories from external sources (Mem0, markdown, JSON)."""
    from .importers import import_from_json, import_from_markdown, import_from_mem0

    path = Path(source_path)
    project = project or _get_project()
    engine = MemoryEngine()

    if fmt == "auto":
        if path.is_dir():
            fmt = "mem0"
        elif path.suffix == ".md":
            fmt = "markdown"
        elif path.suffix == ".json":
            fmt = "json"
        else:
            console.print("[red][ERROR][/red] Could not detect format. Use --format.")
            raise click.Exit(1)

    if fmt == "mem0":
        stats = import_from_mem0(path, engine=engine)
        console.print("[green][OK][/green] Mem0 import complete:")
        console.print(f"  Imported: {stats['imported']}")
        console.print(f"  Skipped: {stats['skipped']}")
    elif fmt == "markdown":
        count = import_from_markdown(path, project, engine=engine)
        console.print(f"[green][OK][/green] Imported {count} memories from markdown")
    elif fmt == "json":
        count = import_from_json(path, project, engine=engine)
        console.print(f"[green][OK][/green] Imported {count} memories from JSON")


@main.command()
@click.argument("milestone")
@click.option("--project", "-p", help="Project name")
@click.option(
    "--platform",
    "-pl",
    multiple=True,
    default=["twitter", "linkedin"],
    help="Platforms to post to",
)
@click.option("--dry-run", is_flag=True, help="Preview without posting")
def post(milestone: str, project: str | None, platform: tuple[str, ...], dry_run: bool) -> None:
    """Post a milestone to social media (requires agent-reach)."""
    from .social import post_milestone

    project = project or _get_project()
    results = post_milestone(project, milestone, list(platform), dry_run=dry_run)

    if dry_run:
        return

    for pl, success in results.items():
        icon = "[green][OK][/green]" if success else "[red][FAIL][/red]"
        console.print(f"{icon} {pl}")


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option(
    "--backend",
    "-b",
    default="tfidf",
    type=click.Choice(["auto", "tfidf", "sentence-transformers"]),
)
@click.option("--output", "-o", type=click.Path(), help="Output JSON file")
def graph(project: str | None, backend: str, output: str | None) -> None:
    """Build and display memory relationship graph."""
    import json

    project = project or _get_project()
    engine = MemoryEngine()
    data = build_memory_graph(engine, project, backend=backend)

    if output:
        Path(output).write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green][OK][/green] Graph written to {output}")
    else:
        console.print(f"[bold]Memory Graph — {project}[/bold]\n")
        console.print(f"Nodes: {len(data['nodes'])}")
        console.print(f"Edges: {len(data['edges'])}")
        if data["edges"]:
            console.print("\nTop connections:")
            for edge in sorted(data["edges"], key=lambda e: e["weight"], reverse=True)[:10]:
                console.print(f"  #{edge['source']} ↔ #{edge['target']} (weight: {edge['weight']})")


if __name__ == "__main__":
    main()
