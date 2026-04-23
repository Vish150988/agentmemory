"""Auto-capture memories from agent sessions, shell history, and git logs."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .core import MemoryEngine, MemoryEntry
from .llm import get_llm_client
from .llm_extract import extract_memories_from_text

CLUADE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Patterns that indicate a meaningful decision/action in shell history
SHELL_DECISION_PATTERNS = [
    (r"^git\s+commit\s+-m\s+[\"'](.+)[\"']", "action", "git commit"),
    (r"^git\s+merge\s+(\S+)", "decision", "git merge"),
    (r"^pip\s+install\s+(.+)", "action", "pip install"),
    (r"^npm\s+install\s+(.+)", "action", "npm install"),
    (r"^cargo\s+add\s+(.+)", "action", "cargo add"),
    (r"^poetry\s+add\s+(.+)", "action", "poetry add"),
    (r"^docker\s+(run|build|compose)\s+(.+)", "action", "docker"),
    (r"^mkdir\s+-p\s+(.+)", "action", "directory created"),
    (r"^mv\s+(.+)\s+(.+)", "action", "file moved"),
    (r"^rm\s+-rf\s+(.+)", "action", "directory removed"),
    (r"^pytest\s+.*", "action", "tests run"),
    (r"^ruff\s+check\s+.*", "action", "linting"),
    (r"^black\s+.*", "action", "formatting"),
]


def _get_powershell_history_path() -> Path | None:
    """Find PowerShell history file."""
    ps_history = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "PowerShell"
        / "PSReadLine"
        / "ConsoleHost_history.txt"
    )
    if ps_history.exists():
        return ps_history
    return None


def _get_bash_history_path() -> Path | None:
    """Find bash history file."""
    bash_history = Path.home() / ".bash_history"
    if bash_history.exists():
        return bash_history
    return None


def capture_from_shell_history(
    project: str,
    limit: int = 50,
    engine: MemoryEngine | None = None,
) -> list[MemoryEntry]:
    """Parse shell history and capture meaningful commands as memories.

    Returns list of captured MemoryEntry objects (not yet stored).
    """
    entries: list[MemoryEntry] = []
    history_path = _get_powershell_history_path() or _get_bash_history_path()

    if not history_path:
        return entries

    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries

    recent_lines = lines[-limit:] if len(lines) > limit else lines
    session_id = f"shell-{project}"

    for line in recent_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        for pattern, category, source_prefix in SHELL_DECISION_PATTERNS:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                content = f"[{source_prefix}] {line}"
                entries.append(
                    MemoryEntry(
                        project=project,
                        session_id=session_id,
                        category=category,
                        content=content,
                        confidence=0.7,
                        source="shell-history",
                        tags="auto-capture,shell",
                    )
                )
                break

    return entries


def capture_from_git_log(
    project: str,
    limit: int = 20,
    cwd: Path | None = None,
    engine: MemoryEngine | None = None,
) -> list[MemoryEntry]:
    """Parse recent git commits and capture them as decision/action memories.

    Returns list of MemoryEntry objects (not yet stored).
    """
    entries: list[MemoryEntry] = []
    cwd = cwd or Path.cwd()

    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=format:%H|%s|%b---END---"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode != 0:
            return entries
    except FileNotFoundError:
        return entries

    commits = result.stdout.split("---END---")
    session_id = f"git-{project}"

    for commit in commits:
        commit = commit.strip()
        if not commit:
            continue
        parts = commit.split("|", 2)
        if len(parts) < 2:
            continue
        commit_hash, subject = parts[0], parts[1]
        body = parts[2] if len(parts) > 2 else ""

        content = subject
        if body.strip():
            content += f"\n{body.strip()[:200]}"

        # Infer category from commit message
        category = "action"
        lower_subject = subject.lower()
        if any(w in lower_subject for w in ["fix", "bug", "issue", "error", "crash"]):
            category = "error"
        elif any(w in lower_subject for w in ["decide", "choose", "select", "use", "switch"]):
            category = "decision"
        elif any(w in lower_subject for w in ["refactor", "clean", "reorganize"]):
            category = "fact"

        entries.append(
            MemoryEntry(
                project=project,
                session_id=session_id,
                category=category,
                content=content,
                confidence=0.8,
                source="git-commit",
                tags=f"auto-capture,git,{commit_hash[:7]}",
            )
        )

    return entries


def _extract_claude_decisions(session_path: Path) -> list[dict[str, Any]]:
    """Extract decision-like messages from a Claude Code JSONL session file."""
    decisions: list[dict[str, Any]] = []
    if not session_path.exists():
        return decisions

    try:
        with session_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "assistant":
                    continue

                message = obj.get("message", {})
                content_blocks = message.get("content", [])
                for block in content_blocks:
                    if block.get("type") != "text":
                        continue
                    text = block.get("text", "")
                    if not text or len(text) < 30:
                        continue

                    # Heuristic: look for decision indicators
                    decision_markers = [
                        "decided",
                        "decision",
                        "choose",
                        "chosen",
                        "approach",
                        "strategy",
                        "plan",
                        "recommend",
                        "suggest",
                        "conclusion",
                        "resolved",
                        "solution",
                        "best practice",
                        "pattern",
                    ]
                    lower_text = text.lower()
                    score = sum(1 for m in decision_markers if m in lower_text)
                    if score >= 2 or (score >= 1 and len(text) < 300):
                        decisions.append(
                            {
                                "text": text[:500],
                                "timestamp": obj.get("timestamp", ""),
                                "score": score,
                            }
                        )
                        break  # One decision per assistant message max
    except OSError:
        pass

    return decisions


def _extract_claude_with_llm(
    session_path: Path,
    project: str,
    session_id: str,
    client: Any | None = None,
) -> list[MemoryEntry]:
    """Use LLM to extract structured memories from a Claude session file."""
    client = client or get_llm_client()
    if not client.is_available():
        return []

    if not session_path.exists():
        return []

    # Read all assistant messages into a single transcript
    transcript_parts: list[str] = []
    try:
        with session_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "assistant":
                    continue
                message = obj.get("message", {})
                for block in message.get("content", []):
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text and len(text) > 20:
                            transcript_parts.append(text)
    except OSError:
        return []

    if not transcript_parts:
        return []

    transcript = "\n\n".join(transcript_parts)
    return extract_memories_from_text(
        transcript,
        project=project,
        session_id=session_id,
        source="claude-code-llm",
        client=client,
    )


def capture_from_claude_logs(
    project: str,
    max_sessions: int = 3,
    engine: MemoryEngine | None = None,
    use_llm: bool = True,
) -> list[MemoryEntry]:
    """Parse recent Claude Code sessions and capture decisions.

    If use_llm=True and an LLM is configured, uses LLM-powered extraction
    for richer structured memories. Falls back to heuristic extraction.

    Returns list of MemoryEntry objects (not yet stored).
    """
    entries: list[MemoryEntry] = []
    base_dir = CLUADE_PROJECTS_DIR

    if not base_dir.exists():
        return entries

    # Find project-specific sessions (Claude names dirs by path)
    project_dirs: list[Path] = []
    for child in base_dir.iterdir():
        if child.is_dir() and project.lower().replace("_", "-") in child.name.lower():
            project_dirs.append(child)

    if not project_dirs:
        # Fallback: scan all projects for any matching sessions
        project_dirs = [d for d in base_dir.iterdir() if d.is_dir()]

    session_files: list[Path] = []
    for pdir in project_dirs:
        for f in pdir.iterdir():
            if f.is_file() and f.suffix == ".jsonl" and len(f.name) > 30:
                session_files.append(f)

    # Sort by mtime, take most recent
    session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    session_files = session_files[:max_sessions]

    for sf in session_files:
        session_id = f"claude-{sf.stem[:8]}"

        # Try LLM extraction first if enabled
        if use_llm:
            llm_entries = _extract_claude_with_llm(sf, project, session_id)
            if llm_entries:
                entries.extend(llm_entries)
                continue

        # Fallback to heuristic extraction
        decisions = _extract_claude_decisions(sf)
        for dec in decisions:
            entries.append(
                MemoryEntry(
                    project=project,
                    session_id=session_id,
                    category="decision",
                    content=dec["text"],
                    confidence=0.6,
                    source="claude-code",
                    tags="auto-capture,claude",
                )
            )

    return entries


def auto_capture_all(
    project: str,
    sources: list[str] | None = None,
    engine: MemoryEngine | None = None,
    cwd: Path | None = None,
    use_llm: bool = True,
) -> dict[str, int]:
    """Run all enabled auto-capture sources and store memories.

    sources: list of 'shell', 'git', 'claude'. Defaults to all.
    use_llm: if True, uses LLM-powered extraction for rich sources (Claude logs).
    Returns counts per source.
    """
    engine = engine or MemoryEngine()
    sources = sources or ["shell", "git", "claude"]
    counts: dict[str, int] = {}

    if "shell" in sources:
        entries = capture_from_shell_history(project, engine=engine)
        for e in entries:
            engine.store(e)
        counts["shell"] = len(entries)

    if "git" in sources:
        entries = capture_from_git_log(project, cwd=cwd, engine=engine)
        for e in entries:
            engine.store(e)
        counts["git"] = len(entries)

    if "claude" in sources:
        entries = capture_from_claude_logs(project, engine=engine, use_llm=use_llm)
        for e in entries:
            engine.store(e)
        counts["claude"] = len(entries)

    return counts
