# Memagent 🧠

> **Open-source cross-agent memory layer for AI coding agents.**

Your AI agent should remember what you built yesterday, why you rejected that approach last week, and that you prefer `async/await` over callbacks.

**Memagent makes that happen.**

[![CI](https://github.com/Vish150988/memagent/actions/workflows/ci.yml/badge.svg)](https://github.com/Vish150988/memagent/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Every time you start a new session with Claude Code, Codex, or Cursor, your agent remembers **nothing**. You re-explain your codebase. You re-teach your preferences. You burn tokens and patience.

**Memagent fixes session amnesia.**

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
| **Team sync** | ✅ | Share memories via `.memagent/` folder in your repo. |
| **MCP server** | ✅ | Expose Memagent as an MCP server for Cursor/Copilot/Claude. |
| **Web dashboard** | ✅ | Browse, search, and manage memories in a local web UI. |
| **Shell integration** | ✅ | Auto-inject context into Claude Code via shell aliases. |
| **Background daemon** | ✅ | Silent auto-capture while you work. |
| **Memory graph** | ✅ | Visualize relationships between memories. |
| **Mem0 importer** | ✅ | Migrate from Mem0 to Memagent. |
| **Social sharing** | ✅ | Auto-post milestones to Twitter/LinkedIn. |
| **VS Code extension** | ✅ | Capture memories directly from your editor. |
| **LLM summarization** | ✅ | GPT/Claude-powered project & session summaries. |
| **Smart auto-tagging** | ✅ | LLM-generated tags for every memory. |
| **Conflict detection** | ✅ | Detect contradictory memories automatically. |
| **REST API** | ✅ | Full HTTP API for any integration. |
| **Backup & restore** | ✅ | Export/import memories, projects, and embeddings as `.zip` or `.json`. |
| **Config file** | ✅ | `~/.memagent/config.yaml` for persistent backend and LLM settings. |
| **FTS5 search** | ✅ | Ranked full-text search with SQLite FTS5 (falls back to LIKE). |

---

## Install

```bash
pip install memagent
# or
pipx install memagent
# or
uv tool install memagent
```

---

## Quick Start

### 1. Initialize memory for your project

```bash
cd my-project
memagent init
```

### 2. Capture memories as you work

```bash
memagent capture "Chose PostgreSQL over MongoDB for ACID compliance" --category decision --confidence 0.95

memagent capture "Always use async/await, never callbacks" --category preference

memagent capture "Auth bug: JWT refresh tokens not rotating" --category error
```

### 3. Find related memories (semantic search)

```bash
memagent related "authentication flow"
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
memagent summarize
```

### 5. Sync to CLAUDE.md

```bash
memagent sync
```

This generates `CLAUDE.md` in your project root. **Claude Code reads it automatically** on startup.

### 6. Install git hooks (auto-sync on commit)

```bash
memagent hook install
```

Now `CLAUDE.md` updates automatically every time you commit.

---

## Full CLI Reference

```bash
# Core memory operations
memagent init                          # Initialize memory for project
memagent capture "content"             # Store a memory
memagent capture "..." --auto-tag      # Auto-generate tags with LLM
memagent recall                        # List recent memories
memagent search "keyword"              # Keyword search
memagent related "query"               # Semantic search
memagent summarize                     # Auto-summarize project
memagent summarize --llm               # LLM-powered rich summary
memagent summarize --session ID        # Summarize one session
memagent digest                        # Weekly digest
memagent digest --llm                  # LLM-powered weekly digest
memagent check-conflicts               # Detect contradictory memories
memagent reinforce <id>                # Boost memory confidence
memagent decay                         # Apply confidence decay
memagent decay --dry-run               # Preview decay

# Auto-capture
memagent capture-auto                  # Auto-capture from git + shell + Claude
memagent capture-auto --dry-run        # Preview what would be captured
memagent capture-auto --sources git    # Only capture from git log

# Agent integration
memagent load                          # Generate context brief
memagent sync                          # Sync to CLAUDE.md
memagent export                        # Export to markdown

# Team sync
memagent team export                   # Export memories to .memagent/
memagent team import                   # Import team-shared memories
memagent team status                   # Show team sync status

# Shell integration
memagent shell show                    # Show shell integration script

# Background daemon
memagent daemon start                  # Start silent auto-capture
memagent daemon status                 # Check daemon status

# Import & migration
memagent import <path> --format mem0   # Import from Mem0
memagent import <path> --format markdown
memagent import <path> --format json

# Social sharing
memagent post "Milestone!"             # Post to Twitter/LinkedIn

# Memory graph
memagent graph                         # Build relationship graph

# MCP server & dashboard & API
memagent mcp                           # Start MCP server (stdio)
memagent dashboard                     # Start web dashboard on :8745
memagent server                        # Start REST API on :8746

# Backup & restore
memagent backup                        # Create dated .zip backup
memagent backup -p my-project          # Backup single project
memagent restore backup.zip            # Restore from backup
memagent restore backup.zip --dry-run  # Preview restore

# Management
memagent stats                         # Show statistics
memagent hook install                  # Install git hooks
memagent hook uninstall                # Remove git hooks
memagent delete <project>              # Wipe project memory
```

---

## How It Works

```
Your Terminal Agent
       │
       ├──► memagent capture "..."   ──► SQLite (~/.memagent/memory.db)
       │
       ├──► memagent capture-auto    ──► Auto-import from git / shell / Claude
       │
       ├──► memagent related "..."   ──► TF-IDF + Cosine Similarity (numpy)
       │
       ├──► memagent load            ──► Markdown brief for agent context
       │
       ├──► memagent sync            ──► CLAUDE.md (auto-read by Claude Code)
       │
       ├──► memagent team export     ──► .memagent/ (git-shared)
       │
       ├──► memagent mcp             ──► MCP server for Cursor/Copilot/Claude
       │
       └──► memagent dashboard       ──► Web UI on http://localhost:8745
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

`CLAUDE.md` is static documentation. Memagent is **learned memory**:

| CLAUDE.md | Memagent |
|-----------|-------------|
| You write it manually | Captured as you work |
| Same every session | Grows and evolves |
| No confidence scoring | Tags confidence + source |
| One file per project | Searchable across all history |
| No semantic search | Find related ideas by meaning |

**Use both.** `CLAUDE.md` for stable conventions. Memagent for dynamic context.

---

## Storage Backends

Memagent supports multiple storage backends. **SQLite is the default** — zero config, works offline, perfect for individuals.

**PostgreSQL** is available for teams, concurrent access, and larger deployments.

### SQLite (default)

```bash
# No configuration needed — works out of the box
memagent init
```

Database file: `~/.memagent/memory.db`

### PostgreSQL

```bash
# 1. Install with PostgreSQL support
pip install memagent[postgres]

# 2. Start PostgreSQL (Docker Compose included)
docker compose up -d

# 3. Set the connection URL
export DATABASE_URL=postgresql://memagent:memagent@localhost:5432/memagent

# 4. Initialize
memagent init
```

### Switching Backends

```python
from memagent import MemoryEngine

# Auto-detect: uses Postgres if DATABASE_URL is set, otherwise SQLite
engine = MemoryEngine()

# Explicit SQLite
engine = MemoryEngine(backend="sqlite")

# Explicit PostgreSQL
engine = MemoryEngine(backend="postgres")
```

### Migrating Data

```bash
# Migrate all memories from SQLite to PostgreSQL
memagent migrate --from-backend sqlite --to-backend postgres

# Migrate a single project
memagent migrate -p my-project --from-backend sqlite --to-backend postgres

# Specify custom source DB or target DSN
memagent migrate --from-db-path ./old.db --to-dsn postgresql://user:pass@host/db
```

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
- [x] Pluggable storage backends (SQLite + PostgreSQL)
- [x] Schema versioning
- [x] Backup & restore
- [x] Config file support
- [x] FTS5 full-text search

---

## Contributing

PRs welcome! This is a community project.

```bash
git clone https://github.com/Vish150988/memagent.git
cd memagent
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT © Open Source Community
