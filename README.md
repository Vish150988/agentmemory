# AgentMemory 🧠

> **Open-source cross-agent memory layer for AI coding agents.**

Your AI agent should remember what you built yesterday, why you rejected that approach last week, and that you prefer `async/await` over callbacks.

**AgentMemory makes that happen.**

[![CI](https://github.com/Vish150988/agentmemory/actions/workflows/ci.yml/badge.svg)](https://github.com/Vish150988/agentmemory/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Every time you start a new session with Claude Code, Codex, or Cursor, your agent remembers **nothing**. You re-explain your codebase. You re-teach your preferences. You burn tokens and patience.

**AgentMemory fixes session amnesia.**

---

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| **Local-first storage** | ✅ | SQLite database on your machine. No cloud. No API keys. |
| **Cross-agent** | ✅ | Works with Claude Code, Codex, Cursor, Gemini CLI, or any agent that reads text. |
| **Semantic search** | ✅ | Find memories by *meaning*, not just keywords. Pure numpy — no heavy deps. |
| **Auto-summarize** | ✅ | Generate project/session summaries automatically. |
| **Confidence decay** | ✅ | Old memories fade. Important ones stick. |
| **Memory reinforcement** | ✅ | Boost confidence when a memory is validated. |
| **CLAUDE.md sync** | ✅ | Auto-generates `CLAUDE.md` from memory. Claude Code reads it automatically. |
| **Git hooks** | ✅ | Auto-sync `CLAUDE.md` on every commit. |
| **Auto-capture** | ✅ | Capture from git log, shell history, and Claude sessions automatically. |
| **Team sync** | ✅ | Share memories via `.agent-memory/` folder in your repo. |
| **MCP server** | ✅ | Expose AgentMemory as an MCP server for Cursor/Copilot/Claude. |
| **Web dashboard** | ✅ | Browse, search, and manage memories in a local web UI. |
| **Shell integration** | ✅ | Auto-inject context into Claude Code via shell aliases. |
| **Background daemon** | ✅ | Silent auto-capture while you work. |
| **Memory graph** | ✅ | Visualize relationships between memories. |
| **Mem0 importer** | ✅ | Migrate from Mem0 to AgentMemory. |
| **Social sharing** | ✅ | Auto-post milestones to Twitter/LinkedIn. |
| **VS Code extension** | ✅ | Capture memories directly from your editor. |

---

## Install

```bash
pip install agentmemory
# or
pipx install agentmemory
# or
uv tool install agentmemory
```

---

## Quick Start

### 1. Initialize memory for your project

```bash
cd my-project
agentmemory init
```

### 2. Capture memories as you work

```bash
agentmemory capture "Chose PostgreSQL over MongoDB for ACID compliance" --category decision --confidence 0.95

agentmemory capture "Always use async/await, never callbacks" --category preference

agentmemory capture "Auth bug: JWT refresh tokens not rotating" --category error
```

### 3. Find related memories (semantic search)

```bash
agentmemory related "authentication flow"
```

Output:
```
┌────┬────────────┬──────────┬────────────────────────────────────────┐
│ ID │ Similarity │ Category │ Content                                │
├────┼────────────┼──────────┼────────────────────────────────────────┤
│ 4  │ 0.58       │ decision │ Chose FastAPI over Django for async    │
└────┴────────────┴──────────┴────────────────────────────────────────┘
```

### 4. Summarize your project

```bash
agentmemory summarize
```

### 5. Sync to CLAUDE.md

```bash
agentmemory sync
```

This generates `CLAUDE.md` in your project root. **Claude Code reads it automatically** on startup.

### 6. Install git hooks (auto-sync on commit)

```bash
agentmemory hook install
```

Now `CLAUDE.md` updates automatically every time you commit.

---

## Full CLI Reference

```bash
# Core memory operations
agentmemory init                          # Initialize memory for project
agentmemory capture "content"             # Store a memory
agentmemory recall                        # List recent memories
agentmemory search "keyword"              # Keyword search
agentmemory related "query"               # Semantic search
agentmemory summarize                     # Auto-summarize project
agentmemory summarize --session ID        # Summarize one session
agentmemory reinforce <id>                # Boost memory confidence
agentmemory decay                         # Apply confidence decay
agentmemory decay --dry-run               # Preview decay

# Auto-capture
agentmemory capture-auto                  # Auto-capture from git + shell + Claude
agentmemory capture-auto --dry-run        # Preview what would be captured
agentmemory capture-auto --sources git    # Only capture from git log

# Agent integration
agentmemory load                          # Generate context brief
agentmemory sync                          # Sync to CLAUDE.md
agentmemory export                        # Export to markdown

# Team sync
agentmemory team export                   # Export memories to .agent-memory/
agentmemory team import                   # Import team-shared memories
agentmemory team status                   # Show team sync status

# Shell integration
agentmemory shell show                    # Show shell integration script

# Background daemon
agentmemory daemon start                  # Start silent auto-capture
agentmemory daemon status                 # Check daemon status

# Import & migration
agentmemory import <path> --format mem0   # Import from Mem0
agentmemory import <path> --format markdown
agentmemory import <path> --format json

# Social sharing
agentmemory post "Milestone!"             # Post to Twitter/LinkedIn

# Memory graph
agentmemory graph                         # Build relationship graph

# MCP server & dashboard
agentmemory mcp                           # Start MCP server (stdio)
agentmemory dashboard                     # Start web dashboard on :8745

# Management
agentmemory stats                         # Show statistics
agentmemory hook install                  # Install git hooks
agentmemory hook uninstall                # Remove git hooks
agentmemory delete <project>              # Wipe project memory
```

---

## How It Works

```
Your Terminal Agent
       │
       ├──► agentmemory capture "..."   ──► SQLite (~/.agent-memory/memory.db)
       │
       ├──► agentmemory capture-auto    ──► Auto-import from git / shell / Claude
       │
       ├──► agentmemory related "..."   ──► TF-IDF + Cosine Similarity (numpy)
       │
       ├──► agentmemory load            ──► Markdown brief for agent context
       │
       ├──► agentmemory sync            ──► CLAUDE.md (auto-read by Claude Code)
       │
       ├──► agentmemory team export     ──► .agent-memory/ (git-shared)
       │
       ├──► agentmemory mcp             ──► MCP server for Cursor/Copilot/Claude
       │
       └──► agentmemory dashboard       ──► Web UI on http://localhost:8745
```

**Storage:** Plain SQLite. Query it with any tool. Back it up. Version it.

**Semantic Search:** Built with TF-IDF + cosine similarity in pure numpy. No scikit-learn, no sentence-transformers, no API calls.

**Privacy:** Nothing leaves your machine.

---

## Memory Categories

| Category | Use For |
|----------|---------|
| `decision` | Architecture choices, tech stack decisions |
| `preference` | Coding style, conventions, personal rules |
| `fact` | Project structure, API behavior, domain knowledge |
| `action` | What you built, refactored, deployed |
| `error` | Bugs, gotchas, things that broke |

---

## Why Not Just Use CLAUDE.md?

`CLAUDE.md` is static documentation. AgentMemory is **learned memory**:

| CLAUDE.md | AgentMemory |
|-----------|-------------|
| You write it manually | Captured as you work |
| Same every session | Grows and evolves |
| No confidence scoring | Tags confidence + source |
| One file per project | Searchable across all history |
| No semantic search | Find related ideas by meaning |

**Use both.** `CLAUDE.md` for stable conventions. AgentMemory for dynamic context.

---

## Roadmap

- [x] Core SQLite engine
- [x] CLI (init, capture, recall, search, load, export)
- [x] Markdown context brief generation
- [x] CLAUDE.md sync
- [x] Git hooks
- [x] Semantic search (TF-IDF + cosine similarity)
- [x] Auto-summarization
- [x] Confidence decay & reinforcement
- [x] Auto-capture from agent sessions
- [x] Team sync (shared memory via git)
- [x] MCP server integration
- [x] Web dashboard
- [x] Shell integration
- [x] Background daemon
- [x] Memory graph visualization
- [x] Mem0 importer
- [x] Social sharing
- [x] VS Code extension

---

## Contributing

PRs welcome! This is a community project.

```bash
git clone https://github.com/Vish150988/agentmemory.git
cd agentmemory
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT © Open Source Community
