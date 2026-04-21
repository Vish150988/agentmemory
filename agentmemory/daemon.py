"""Background daemon for silent auto-capture.

Watches for file changes, git commits, and session activity.
Requires: pip install watchdog (optional, falls back to polling)
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .core import MemoryEngine, MemoryEntry

# Default paths to watch
WATCH_PATTERNS = ["*.py", "*.js", "*.ts", "*.md", "*.json", "*.toml", "*.yaml", "*.yml"]
IGNORE_PATTERNS = [".git", "__pycache__", "node_modules", ".venv", "venv", "*.pyc"]

# Minimum seconds between captures for the same file
DEBOUNCE_SECONDS = 30.0


@dataclass
class DaemonConfig:
    project: str
    watch_dir: Path
    interval: float = 60.0
    capture_git: bool = True
    capture_files: bool = True
    db_path: Optional[Path] = None


class MemoryDaemon:
    """Background daemon that silently captures memories."""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self.engine = MemoryEngine(db_path=config.db_path)
        self._stop_event = threading.Event()
        self._last_capture: dict[str, float] = {}
        self._last_git_head: str = ""
        self._thread: threading.Thread | None = None

    def _should_capture(self, key: str) -> bool:
        now = time.time()
        last = self._last_capture.get(key, 0)
        if now - last < DEBOUNCE_SECONDS:
            return False
        self._last_capture[key] = now
        return True

    def _get_git_head(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.config.watch_dir,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except FileNotFoundError:
            return ""

    def _capture_git_changes(self) -> int:
        if not self.config.capture_git:
            return 0

        current_head = self._get_git_head()
        if not current_head or current_head == self._last_git_head:
            return 0

        self._last_git_head = current_head

        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%s|%b"],
                cwd=self.config.watch_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return 0
        except FileNotFoundError:
            return 0

        parts = result.stdout.split("|", 1)
        subject = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else ""

        if not subject:
            return 0

        # Infer category
        category = "action"
        lower = subject.lower()
        if any(w in lower for w in ["fix", "bug", "crash", "error"]):
            category = "error"
        elif any(w in lower for w in ["decide", "choose", "select", "use", "switch", "migrate"]):
            category = "decision"

        content = subject
        if body:
            content += f"\n{body[:200]}"

        entry = MemoryEntry(
            project=self.config.project,
            session_id="daemon",
            category=category,
            content=content,
            confidence=0.75,
            source="daemon-git",
            tags="auto-capture,daemon,git",
        )
        self.engine.store(entry)
        return 1

    def _capture_file_changes(self) -> int:
        if not self.config.capture_files:
            return 0

        count = 0
        for pattern in WATCH_PATTERNS:
            for file_path in self.config.watch_dir.rglob(pattern):
                # Skip ignored directories
                if any(part.startswith(".") or part in IGNORE_PATTERNS for part in file_path.parts):
                    continue

                key = str(file_path)
                if not self._should_capture(key):
                    continue

                try:
                    mtime = file_path.stat().st_mtime
                    # Only capture if modified recently
                    if time.time() - mtime > self.config.interval * 2:
                        continue
                except OSError:
                    continue

                # Don't capture every file change, just significant ones
                # Heuristic: only capture if it's a config or docs file
                if file_path.suffix not in (".md", ".toml", ".yaml", ".yml", ".json"):
                    continue

                entry = MemoryEntry(
                    project=self.config.project,
                    session_id="daemon",
                    category="action",
                    content=f"Modified {file_path.name}",
                    confidence=0.5,
                    source="daemon-file",
                    tags=f"auto-capture,daemon,file,{file_path.suffix.lstrip('.')}",
                )
                self.engine.store(entry)
                count += 1
                if count >= 3:  # Max 3 file captures per cycle
                    break

        return count

    def _run_cycle(self) -> dict[str, int]:
        git_captures = self._capture_git_changes()
        file_captures = self._capture_file_changes()
        return {"git": git_captures, "files": file_captures}

    def start(self) -> None:
        """Start the daemon in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._run_cycle()
            self._stop_event.wait(self.config.interval)

    def stop(self) -> None:
        """Stop the daemon."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# Global daemon instance for CLI management
_daemon_instance: MemoryDaemon | None = None


def start_daemon(project: str, cwd: Path | None = None, interval: float = 60.0) -> MemoryDaemon:
    """Start the background daemon."""
    global _daemon_instance
    cwd = cwd or Path.cwd()
    config = DaemonConfig(project=project, watch_dir=cwd, interval=interval)
    _daemon_instance = MemoryDaemon(config)
    _daemon_instance.start()
    return _daemon_instance


def stop_daemon() -> None:
    """Stop the background daemon."""
    global _daemon_instance
    if _daemon_instance:
        _daemon_instance.stop()
        _daemon_instance = None


def daemon_status() -> dict[str, Any]:
    """Get daemon status."""
    global _daemon_instance
    if _daemon_instance is None:
        return {"running": False}
    return {
        "running": _daemon_instance.is_running(),
        "project": _daemon_instance.config.project,
        "watch_dir": str(_daemon_instance.config.watch_dir),
        "interval": _daemon_instance.config.interval,
    }
