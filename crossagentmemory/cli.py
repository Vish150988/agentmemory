"""CLI interface for CrossAgentMemory."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

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
@click.version_option(version="0.4.0")
def main() -> None:
    """CrossAgentMemory — Cross-agent memory layer for AI coding agents."""
    pass


@main.command()
@click.option("--project", "-p", help="Project name (auto-detected by default)")
@click.option(
    "--backend",
    "-b",
    default="auto",
    type=click.Choice(["auto", "sqlite", "postgres"]),
    help="Storage backend",
)
def init(project: str | None, backend: str) -> None:
    """Initialize agent memory for the current project."""
    project = project or _get_project()
    engine = MemoryEngine(backend=backend)

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
    db_info = (
        os.environ.get("DATABASE_URL", "localhost")
        if backend in ("auto", "postgres")
        else str(DEFAULT_MEMORY_DIR / "memory.db")
    )
    console.print(f"  Backend: {backend} ({db_info})")


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
@click.option("--auto-tag", is_flag=True, help="Auto-generate tags using LLM")
@click.option("--user", "-u", default="", help="User ID (multi-tenant)")
@click.option("--tenant", default="", help="Tenant/organization ID")
@click.option("--valid-from", default="", help="ISO timestamp when this memory becomes valid")
@click.option("--valid-until", default="", help="ISO timestamp when this memory expires")
@click.option(
    "--llm-extract", is_flag=True, help="Use LLM to extract structured memories from content"
)
def capture(
    content: str,
    project: str | None,
    category: str,
    confidence: float,
    tags: str,
    source: str,
    auto_tag: bool,
    user: str,
    tenant: str,
    valid_from: str,
    valid_until: str,
    llm_extract: bool,
) -> None:
    """Capture a memory entry."""
    project = project or _get_project()
    engine = MemoryEngine()

    session_id = os.environ.get("CROSSAGENTMEMORY_SESSION", str(uuid.uuid4())[:8])

    if auto_tag and not tags:
        from .llm_features import auto_tag_memory

        generated = auto_tag_memory(content)
        if generated:
            tags = ",".join(generated)

    if llm_extract:
        from .llm_extract import extract_and_store

        ids = extract_and_store(
            content,
            engine,
            project=project,
            session_id=session_id,
            source=source,
        )
        console.print(
            f"[green][OK][/green] LLM extracted [bold]{len(ids)}[/bold] memories"
            f" in [bold]{project}[/bold]"
        )
        return

    entry = MemoryEntry(
        project=project,
        session_id=session_id,
        category=category,
        content=content,
        confidence=confidence,
        source=source,
        tags=tags,
        user_id=user,
        tenant_id=tenant,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    memory_id = engine.store(entry)
    tag_info = f" [dim](tags: {tags})[/dim]" if tags else ""
    console.print(
        f"[green][OK][/green] Captured memory [bold]#{memory_id}[/bold]"
        f" in [bold]{project}[/bold]{tag_info}"
    )


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--category", "-c", help="Filter by category")
@click.option("--limit", "-n", default=20, help="Number of memories to show")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--tenant", default=None, help="Filter by tenant ID")
@click.option("--at-time", default=None, help="ISO timestamp: only memories valid at this time")
def recall(
    project: str | None,
    category: str | None,
    limit: int,
    user: str | None,
    tenant: str | None,
    at_time: str | None,
) -> None:
    """Recall recent memories."""
    project = project or _get_project()
    engine = MemoryEngine()
    memories = engine.recall(
        project=project,
        category=category,
        limit=limit,
        user_id=user,
        tenant_id=tenant,
        at_time=at_time,
    )

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


@main.command("recall-temporal")
@click.option("--project", "-p", help="Project name")
@click.option("--at-time", default=None, help="ISO timestamp: memories valid at this instant")
@click.option("--window-start", default=None, help="ISO timestamp: start of validity window")
@click.option("--window-end", default=None, help="ISO timestamp: end of validity window")
@click.option("--limit", "-n", default=20, help="Number of memories to show")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--tenant", default=None, help="Filter by tenant ID")
def recall_temporal(
    project: str | None,
    at_time: str | None,
    window_start: str | None,
    window_end: str | None,
    limit: int,
    user: str | None,
    tenant: str | None,
) -> None:
    """Recall memories with temporal window filtering.

    Examples:
        cam recall-temporal --at-time 2024-03-15T00:00:00Z
        cam recall-temporal --window-start 2024-01-01 --window-end 2024-06-01
    """
    project = project or _get_project()
    engine = MemoryEngine()
    memories = engine.recall_temporal(
        project=project,
        at_time=at_time,
        window_start=window_start,
        window_end=window_end,
        limit=limit,
    )

    # Post-filter by user/tenant since backend may not handle all combinations
    if user:
        memories = [m for m in memories if m.user_id == user]
    if tenant:
        memories = [m for m in memories if m.tenant_id == tenant]

    if not memories:
        console.print(
            f"[yellow]No temporally valid memories found for project '{project}'[/yellow]"
        )
        return

    table = Table(title=f"Temporal Memories — {project}")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Category", width=12)
    table.add_column("Content")
    table.add_column("Valid From", width=12)
    table.add_column("Valid Until", width=12)

    for m in memories:
        vf = m.valid_from[:10] if m.valid_from else "—"
        vu = m.valid_until[:10] if m.valid_until else "—"
        table.add_row(
            str(m.id),
            f"[bold]{m.category}[/bold]",
            m.content[:80] + ("..." if len(m.content) > 80 else ""),
            vf,
            vu,
        )

    console.print(table)


@main.command()
@click.argument("keyword")
@click.option("--project", "-p", help="Project name")
@click.option("--limit", "-n", default=10)
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--tenant", default=None, help="Filter by tenant ID")
@click.option("--at-time", default=None, help="ISO timestamp: only memories valid at this time")
def search(
    keyword: str,
    project: str | None,
    limit: int,
    user: str | None,
    tenant: str | None,
    at_time: str | None,
) -> None:
    """Search memories by keyword."""
    project = project or _get_project()
    engine = MemoryEngine()
    results = engine.search(
        keyword,
        project=project,
        limit=limit,
        user_id=user,
        tenant_id=tenant,
        at_time=at_time,
    )

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
    """Export memories to .crossagentmemory/ for team sharing."""
    project = project or _get_project()
    path = team_export(project, cwd=Path(cwd))
    console.print(f"[green][OK][/green] Exported team memory to [bold]{path}[/bold]")
    console.print("[dim]Commit the .crossagentmemory/ folder to share with your team.[/dim]")


@team.command("import")
@click.option("--project", "-p", help="Project name")
@click.option("--cwd", type=click.Path(), default=".", help="Project directory")
@click.option("--dry-run", is_flag=True, help="Preview without importing")
def team_import_cmd(project: str | None, cwd: str, dry_run: bool) -> None:
    """Import team-shared memories from .crossagentmemory/."""
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
    if info["latest_export"]:
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
@click.option(
    "--use-llm",
    is_flag=True,
    default=True,
    help="Use LLM extraction for rich sources (Claude logs)",
)
def capture_auto(project: str | None, sources: str, dry_run: bool, use_llm: bool) -> None:
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
            entries.extend(capture_from_claude_logs(project, use_llm=use_llm))
        console.print(f"[bold]Dry run — would capture {len(entries)} memories:[/bold]\n")
        for e in entries[:10]:
            console.print(f"  [{e.category}] {e.content[:80]}...")
        if len(entries) > 10:
            console.print(f"  ... and {len(entries) - 10} more")
        return

    counts = auto_capture_all(project, sources=source_list, use_llm=use_llm)
    total = sum(counts.values())
    console.print(f"[green][OK][/green] Auto-captured [bold]{total}[/bold] memories:")
    for src, count in counts.items():
        console.print(f"  {src}: {count}")


@main.command()
def mcp() -> None:
    """Start the crossagentmemory mcp server (stdio)."""
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
    """Start the CrossAgentMemory web dashboard."""
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
    """Manage git hooks for CrossAgentMemory."""
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
    """Remove CrossAgentMemory git hooks."""
    uninstall_hooks()
    console.print("[green][OK][/green] Removed CrossAgentMemory git hooks.")


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

    console.print("[bold]crossagentmemory stats[/bold]\n")
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
@click.option("--llm", is_flag=True, help="Use LLM for richer summary")
def summarize(project: str | None, session: str | None, output: str | None, llm: bool) -> None:
    """Summarize memories (session or entire project)."""
    project = project or _get_project()
    engine = MemoryEngine()

    if llm:
        from .llm_features import summarize_project_llm, summarize_session_llm

        if session:
            text = summarize_session_llm(engine, session, project)
            title = f"Session: {session}"
        else:
            text = summarize_project_llm(engine, project)
            title = f"Project: {project}"
    else:
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
    type=click.Choice(["auto", "mem0", "markdown", "json", "obsidian", "notion"]),
)
@click.option("--project", "-p", help="Target project name")
def import_(source_path: str, fmt: str, project: str | None) -> None:
    """Import memories from external sources (Mem0, markdown, JSON, Obsidian, Notion)."""
    from .importers import (
        import_from_json,
        import_from_markdown,
        import_from_mem0,
        import_from_notion,
        import_from_obsidian,
    )

    path = Path(source_path)
    project = project or _get_project()
    engine = MemoryEngine()

    if fmt == "auto":
        if path.is_dir():
            # Check for Obsidian vault markers (.obsidian folder)
            if (path / ".obsidian").exists():
                fmt = "obsidian"
            else:
                fmt = "mem0"
        elif path.suffix == ".md":
            fmt = "markdown"
        elif path.suffix == ".json":
            fmt = "json"
        elif path.suffix == ".zip":
            fmt = "notion"
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
    elif fmt == "obsidian":
        count = import_from_obsidian(path, project=project, engine=engine)
        console.print(f"[green][OK][/green] Imported {count} memories from Obsidian vault")
    elif fmt == "notion":
        count = import_from_notion(path, project=project, engine=engine)
        console.print(f"[green][OK][/green] Imported {count} memories from Notion export")


@main.command()
@click.option("--from-backend", "-f", default="sqlite", type=click.Choice(["sqlite", "postgres"]))
@click.option("--to-backend", "-t", default="postgres", type=click.Choice(["sqlite", "postgres"]))
@click.option("--from-db-path", type=click.Path(), help="Source SQLite DB path")
@click.option("--to-dsn", help="Target PostgreSQL DSN")
@click.option("--project", "-p", help="Project to migrate (default: all)")
def migrate(
    from_backend: str,
    to_backend: str,
    from_db_path: str | None,
    to_dsn: str | None,
    project: str | None,
) -> None:
    """Migrate memories from one backend to another."""
    if from_backend == to_backend:
        console.print("[yellow]Source and target backend are the same. Nothing to do.[/yellow]")
        return

    # Set up source engine
    source_kwargs: dict[str, Any] = {"backend": from_backend}
    if from_db_path:
        source_kwargs["db_path"] = Path(from_db_path)

    # Set up target engine
    target_kwargs: dict[str, Any] = {"backend": to_backend}
    if to_dsn:
        os.environ["DATABASE_URL"] = to_dsn

    try:
        source = MemoryEngine(**source_kwargs)
        target = MemoryEngine(**target_kwargs)
    except ImportError as e:
        console.print(f"[red][ERROR][/red] {e}")
        raise click.Exit(1)

    # Collect memories
    if project:
        memories = source.recall(project=project, limit=100_000)
        projects = [project]
    else:
        memories = source.recall(limit=100_000)
        projects = source.list_projects()

    # Migrate memories
    imported = 0
    id_map: dict[int, int] = {}
    for m in memories:
        old_id = m.id
        m.id = None
        new_id = target.store(m)
        if old_id is not None:
            id_map[old_id] = new_id
        imported += 1

    # Migrate embeddings
    for proj in projects:
        # Try common model names; backends may vary
        for model_name in ("tfidf", "sentence-transformers"):
            try:
                embeddings = source.get_embeddings(proj, model_name)
                for old_id, emb in embeddings:
                    new_id = id_map.get(old_id)
                    if new_id:
                        target.store_embedding(new_id, model_name, emb)
            except Exception:
                pass

    # Migrate project contexts
    for proj in projects:
        ctx = source.get_project_context(proj)
        desc = source.get_project_description(proj)
        if ctx or desc:
            target.set_project_context(proj, ctx or {}, description=desc)

    console.print(f"[green][OK][/green] Migrated [bold]{imported}[/bold] memories")
    console.print(f"  From: {from_backend}")
    console.print(f"  To: {to_backend}")
    if projects:
        console.print(f"  Projects: {', '.join(projects)}")


@main.command()
@click.option("--project", "-p", help="Project to backup (default: all)")
@click.option("--output", "-o", type=click.Path(), help="Output file (.zip or .json)")
def backup(project: str | None, output: str | None) -> None:
    """Create a backup of memories, projects, and embeddings."""
    from .backup import create_backup

    project = project or _get_project()
    engine = MemoryEngine()

    date_str = __import__("datetime").datetime.now().strftime("%Y%m%d")
    default_name = f"crossagentmemory-backup-{project or 'all'}-{date_str}.zip"
    out_path = Path(output) if output else Path.cwd() / default_name

    stats = create_backup(engine, out_path, project=project)
    console.print(f"[green][OK][/green] Backup created: [bold]{stats['path']}[/bold]")
    console.print(f"  Memories: {stats['memories']}")
    console.print(f"  Projects: {stats['projects']}")
    console.print(f"  Embeddings: {stats['embeddings']}")


@main.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Preview without restoring")
def restore(input_path: str, dry_run: bool) -> None:
    """Restore memories, projects, and embeddings from a backup."""
    from .backup import restore_backup

    engine = MemoryEngine()
    stats = restore_backup(engine, Path(input_path), dry_run=dry_run)

    if dry_run:
        console.print(f"[yellow][DRY RUN][/yellow] Would restore from [bold]{input_path}[/bold]")
        console.print(f"  Memories: {stats['memories']}")
        console.print(f"  Projects: {stats['projects']}")
        console.print(f"  Embeddings: {stats['embeddings']}")
        return

    console.print(f"[green][OK][/green] Restored from [bold]{input_path}[/bold]")
    console.print(f"  Memories: {stats['memories']}")
    console.print(f"  Projects: {stats['projects']}")
    console.print(f"  Embeddings: {stats['embeddings']}")


@main.command("cloud-export")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3-compatible endpoint URL (e.g. https://...)")
@click.option("--key", default="crossagentmemory-backup.enc", help="Object key in bucket")
@click.option(
    "--password-env",
    default="CROSSAGENTMEMORY_SYNC_PASSWORD",
    help="Env var containing encryption password",
)
def cloud_export(bucket: str, endpoint: str | None, key: str, password_env: str) -> None:
    """Export encrypted memories to S3-compatible cloud storage."""
    from .cloud_sync import sync_export

    password = os.environ.get(password_env)
    if not password:
        console.print(f"[red][ERROR][/red] Set {password_env} environment variable")
        raise click.Exit(1)

    engine = MemoryEngine()
    sync_export(engine, password, bucket, endpoint=endpoint, key=key)
    console.print(f"[green][OK][/green] Uploaded encrypted backup to s3://{bucket}/{key}")


@main.command("cloud-import")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3-compatible endpoint URL")
@click.option("--key", default="crossagentmemory-backup.enc", help="Object key in bucket")
@click.option(
    "--password-env",
    default="CROSSAGENTMEMORY_SYNC_PASSWORD",
    help="Env var containing encryption password",
)
def cloud_import(bucket: str, endpoint: str | None, key: str, password_env: str) -> None:
    """Import encrypted memories from S3-compatible cloud storage."""
    from .cloud_sync import sync_import

    password = os.environ.get(password_env)
    if not password:
        console.print(f"[red][ERROR][/red] Set {password_env} environment variable")
        raise click.Exit(1)

    engine = MemoryEngine()
    count = sync_import(engine, password, bucket, endpoint=endpoint, key=key)
    console.print(f"[green][OK][/green] Restored {count} memories from s3://{bucket}/{key}")


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


@main.command()
@click.option("--project", "-p", help="Project name")
@click.option("--output", "-o", type=click.Path(), help="Output file")
@click.option("--llm", is_flag=True, help="Use LLM for richer digest")
def digest(project: str | None, output: str | None, llm: bool) -> None:
    """Generate weekly digest of memories."""
    from .llm_features import generate_weekly_digest
    from .summarize import summarize_project

    project = project or _get_project()
    engine = MemoryEngine()

    if llm:
        text = generate_weekly_digest(engine, project=project)
    else:
        text = summarize_project(engine, project)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green][OK][/green] Digest written to {output}")
    else:
        console.print(f"\n[bold cyan]--- Weekly Digest — {project} ---[/bold cyan]\n")
        console.print(text)


@main.command("check-conflicts")
@click.option("--project", "-p", help="Project name")
def check_conflicts(project: str | None) -> None:
    """Detect contradictory memories."""
    from .llm_features import detect_conflicts

    project = project or _get_project()
    engine = MemoryEngine()
    conflicts = detect_conflicts(engine, project)

    if not conflicts:
        console.print(f"[green][OK][/green] No contradictions found in '{project}'")
        return

    console.print(f"[yellow]Found {len(conflicts)} potential contradiction(s):[/yellow]\n")
    table = Table(title=f"Contradictions — {project}")
    table.add_column("Memory A", style="dim", width=6)
    table.add_column("Memory B", style="dim", width=6)
    table.add_column("Reason")

    for c in conflicts:
        table.add_row(str(c["a"]), str(c["b"]), c["reason"])

    console.print(table)


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8746, help="Port to bind")
def server(host: str, port: int) -> None:
    """Start the CrossAgentMemory REST API server."""
    try:
        from .server import run_server
    except ImportError as e:
        console.print(f"[red][ERROR][/red] {e}")
        console.print("[dim]Install with: pip install fastapi uvicorn[/dim]")
        raise click.Exit(1)
    console.print(f"[green][OK][/green] Starting REST API at http://{host}:{port}")
    console.print("[dim]Endpoints: /api/memories, /api/search, /api/summarize, /api/digest[/dim]")
    run_server(host=host, port=port)


if __name__ == "__main__":
    main()
