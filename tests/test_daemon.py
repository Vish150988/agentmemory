"""Tests for background daemon."""

from __future__ import annotations

from pathlib import Path

from agentmemory.daemon import DaemonConfig, MemoryDaemon, daemon_status


def test_daemon_config() -> None:
    config = DaemonConfig(project="test", watch_dir=Path.cwd())
    assert config.project == "test"
    assert config.interval == 60.0


def test_daemon_status_not_running() -> None:
    status = daemon_status()
    assert status["running"] is False


def test_daemon_capture_git_changes(tmp_path: Path) -> None:
    import subprocess

    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=tmp_path,
        capture_output=True,
    )
    (tmp_path / "a.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test commit"],
        cwd=tmp_path,
        capture_output=True,
    )

    db = tmp_path / "test.db"
    config = DaemonConfig(project="test", watch_dir=tmp_path, db_path=db)
    daemon = MemoryDaemon(config)
    count = daemon._capture_git_changes()
    assert count == 1
