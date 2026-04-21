"""Tests for social media integration."""

from __future__ import annotations

from agentmemory.social import post_milestone


def test_post_milestone_dry_run() -> None:
    results = post_milestone("test", "Milestone reached", platforms=["twitter"], dry_run=True)
    assert results == {"twitter": False}


def test_post_milestone_no_agent_reach() -> None:
    # Should fail gracefully if agent-reach not installed
    results = post_milestone("test", "Milestone reached", platforms=["twitter"], dry_run=False)
    assert results["twitter"] is False
