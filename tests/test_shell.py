"""Tests for shell integration."""

from __future__ import annotations

from agentmemory.shell import _get_shell_config_path, detect_shell, generate_shell_integration


def test_detect_shell_returns_string() -> None:
    result = detect_shell()
    assert isinstance(result, str)
    assert result in ("bash", "zsh", "fish", "powershell")


def test_generate_shell_integration_bash() -> None:
    script = generate_shell_integration("bash")
    assert "claude()" in script
    assert "amc()" in script
    assert "agentmemory capture" in script


def test_generate_shell_integration_zsh() -> None:
    script = generate_shell_integration("zsh")
    assert "claude()" in script
    assert "alias amc" in script


def test_generate_shell_integration_powershell() -> None:
    script = generate_shell_integration("powershell")
    assert "function claude" in script
    assert "function amc" in script


def test_get_shell_config_path() -> None:
    path = _get_shell_config_path("bash")
    assert path.name == ".bashrc"
    path = _get_shell_config_path("zsh")
    assert path.name == ".zshrc"
