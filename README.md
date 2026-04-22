# CrossAgentMemory 🧠

> **Open-source cross-agent memory layer for AI coding agents.**

Your AI agent should remember what you built yesterday, why you rejected that approach last week, and that you prefer `async/await` over callbacks.

**CrossAgentMemory makes that happen.**

[![CI](https://github.com/Vish150988/crossagentmemory/actions/workflows/ci.yml/badge.svg)](https://github.com/Vish150988/crossagentmemory/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Every time you start a new session with Claude Code, Codex, or Cursor, your agent remembers **nothing**. You re-explain your codebase. You re-teach your preferences. You burn tokens and patience.

**CrossAgentMemory fixes session amnesia.**

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
| **Team sync** | ✅ | Share memories via `.crossagentmemory/` folder in your repo. |
| **MCP server** | ✅ | Expose CrossAgentMemory as an MCP server for Cursor/Copilot/Claude. |
| **Web dashboard** | ✅ | Browse, search, and manage memories in a local web UI. |
| **Shell integration** | ✅ | Auto-inject context into Claude Code via shell aliases. |
| **Background daemon** | ✅ | Silent auto-capture while you work. |
| **Memory graph** | ✅ | Visualize relationships between memories. |
| **Mem0 importer** | ✅ | Migrate from Mem0 to CrossAgentMemory. |
| **Obsidian/Notion importer** | ✅ | Import from Obsidian vaults and Notion exports. |
| **Chroma backend** | ✅ | Native vector DB backend with semantic search. |
| **Redis backend** | ✅ | Fast in-memory backend for high-throughput use. |
| **Cloud sync** | ✅ | Encrypted S3/R2 backup and restore. |
| **Social sharing** | ✅ | Auto-post milestones to Twitter/LinkedIn. |
| **VS Code extension** | ✅ | Capture memories directly from your editor. |
| **LLM summarization** | ✅ | GPT/Claude-powered project & session summaries. |
| **Smart auto-tagging** | ✅ | LLM-generated tags for every memory. |
| **Conflict detection** | ✅ | Detect contradictory memories automatically. |
| **REST API** | ✅ | Full HTTP API for any integration. |
| **Backup & restore** | ✅ | Export/import memories, projects, and embeddings as `.zip` or `.json`. |
| **Config file** | ✅ | `~/.crossagentmemory/config.yaml` for persistent backend and LLM settings. |
| **FTS5 search** | ✅ | Ranked full-text search with SQLite FTS5 (falls back to LIKE). |

---

## Install

```bash
pip install crossagentmemory
# or
pipx install crossagentmemory
# or
uv tool install crossagentmemory
```

---

## Quick Start

### 1. Initialize memory for your project

```bash
cd my-project
crossagentmemory init
```

### 2. Capture memories as you work

```bash
crossagentmemory capture "Chose PostgreSQL over MongoDB for ACID compliance" --category decision --confidence 0.95

crossagentmemory capture "Always use async/await, never callbacks" --category preference

crossagentmemory capture "Auth bug: JWT refresh tokens not rotating" --category error
```

### 3. Find related memories (semantic search)

```bash
crossagentmemory related "authentication flow"
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
crossagentmemory summarize
```

### 5. Sync to CLAUDE.md

```bash
crossagentmemory sync
```

This generates `CLAUDE.md` in your project root. **Claude Code reads it automatically** on startup.

### 6. Install git hooks (auto-sync on commit)

```bash
crossagentmemory hook install
```

Now `CLAUDE.md` updates automatically every time you commit.

---

## Full CLI Reference

```bash
# Core memory operations
crossagentmemory init                          # Initialize memory for project
crossagentmemory capture "content"             # Store a memory
crossagentmemory capture "..." --auto-tag      # Auto-generate tags with LLM
crossagentmemory recall                        # List recent memories
crossagentmemory search "keyword"              # Keyword search
crossagentmemory related "query"               # Semantic search
crossagentmemory summarize                     # Auto-summarize project
crossagentmemory summarize --llm               # LLM-powered rich summary
crossagentmemory summarize --session ID        # Summarize one session
crossagentmemory digest                        # Weekly digest
crossagentmemory digest --llm                  # LLM-powered weekly digest
crossagentmemory check-conflicts               # Detect contradictory memories
crossagentmemory reinforce <id>                # Boost memory confidence
crossagentmemory decay                         # Apply confidence decay
crossagentmemory decay --dry-run               # Preview decay

# Auto-capture
crossagentmemory capture-auto                  # Auto-capture from git + shell + Claude
crossagentmemory capture-auto --dry-run        # Preview what would be captured
crossagentmemory capture-auto --sources git    # Only capture from git log

# Agent integration
crossagentmemory load                          # Generate context brief
crossagentmemory sync                          # Sync to CLAUDE.md
crossagentmemory export                        # Export to markdown

# Team sync
crossagentmemory team export                   # Export memories to .crossagentmemory/
crossagentmemory team import                   # Import team-shared memories
crossagentmemory team status                   # Show team sync status

# Shell integration
crossagentmemory shell show                    # Show shell integration script

# Background daemon
crossagentmemory daemon start                  # Start silent auto-capture
crossagentmemory daemon status                 # Check daemon status

# Import & migration
crossagentmemory import <path> --format mem0       # Import from Mem0
crossagentmemory import <path> --format markdown
crossagentmemory import <path> --format json
crossagentmemory import <vault> --format obsidian  # Import Obsidian vault
crossagentmemory import <export.zip> --format notion # Import Notion export

# Social sharing
crossagentmemory post "Milestone!"             # Post to Twitter/LinkedIn

# Memory graph
crossagentmemory graph                         # Build relationship graph

# MCP server & dashboard & API
crossagentmemory mcp                           # Start MCP server (stdio)
crossagentmemory dashboard                     # Start web dashboard on :8745
crossagentmemory server                        # Start REST API on :8746

# Backup & restore
crossagentmemory backup                            # Create dated .zip backup
crossagentmemory backup -p my-project              # Backup single project
crossagentmemory restore backup.zip                # Restore from backup
crossagentmemory restore backup.zip --dry-run      # Preview restore
crossagentmemory cloud-export --bucket my-bucket   # Upload encrypted backup to S3
crossagentmemory cloud-import --bucket my-bucket   # Restore from encrypted S3 backup

# Management
crossagentmemory stats                         # Show statistics
crossagentmemory hook install                  # Install git hooks
crossagentmemory hook uninstall                # Remove git hooks
crossagentmemory delete <project>              # Wipe project memory
```

---

## How It Works

```
Your Terminal Agent
       │
       ├──► crossagentmemory capture "..."   ──► SQLite (~/.crossagentmemory/memory.db)
       │
       ├──► crossagentmemory capture-auto    ──► Auto-import from git / shell / Claude
       │
       ├──► crossagentmemory related "..."   ──► TF-IDF + Cosine Similarity (numpy)
       │
       ├──► crossagentmemory load            ──► Markdown brief for agent context
       │
       ├──► crossagentmemory sync            ──► CLAUDE.md (auto-read by Claude Code)
       │
       ├──► crossagentmemory team export     ──► .crossagentmemory/ (git-shared)
       │
       ├──► crossagentmemory mcp             ──► MCP server for Cursor/Copilot/Claude
       │
       └──► crossagentmemory dashboard       ──► Web UI on http://localhost:8745
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

`CLAUDE.md` is static documentation. CrossAgentMemory is **learned memory**:

| CLAUDE.md | CrossAgentMemory |
|-----------|-------------|
| You write it manually | Captured as you work |
| Same every session | Grows and evolves |
| No confidence scoring | Tags confidence + source |
| One file per project | Searchable across all history |
| No semantic search | Find related ideas by meaning |

**Use both.** `CLAUDE.md` for stable conventions. CrossAgentMemory for dynamic context.

---

## Storage Backends

CrossAgentMemory supports multiple storage backends. **SQLite is the default** — zero config, works offline, perfect for individuals.

**PostgreSQL** is available for teams, concurrent access, and larger deployments.

### SQLite (default)

```bash
# No configuration needed — works out of the box
crossagentmemory init
```

Database file: `~/.crossagentmemory/memory.db`

### PostgreSQL

```bash
# 1. Install with PostgreSQL support
pip install crossagentmemory[postgres]

# 2. Start PostgreSQL (Docker Compose included)
docker compose up -d

# 3. Set the connection URL
export DATABASE_URL=postgresql://crossagentmemory:crossagentmemory@localhost:5432/crossagentmemory

# 4. Initialize
crossagentmemory init
```

### Chroma (vector DB)

```bash
# 1. Install with Chroma support
pip install crossagentmemory[chroma]

# 2. Use Chroma backend
engine = MemoryEngine(backend="chroma")
```

### Redis

```bash
# 1. Install with Redis support
pip install crossagentmemory[redis]

# 2. Use Redis backend (expects Redis on localhost:6379)
engine = MemoryEngine(backend="redis")
```

### Switching Backends

```python
from crossagentmemory import MemoryEngine

# Auto-detect: uses Postgres if DATABASE_URL is set, otherwise SQLite
engine = MemoryEngine()

# Explicit SQLite
engine = MemoryEngine(backend="sqlite")

# Explicit PostgreSQL
engine = MemoryEngine(backend="postgres")

# Chroma vector DB
engine = MemoryEngine(backend="chroma")

# Redis
engine = MemoryEngine(backend="redis")
```

### Migrating Data

```bash
# Migrate all memories from SQLite to PostgreSQL
crossagentmemory migrate --from-backend sqlite --to-backend postgres

# Migrate a single project
crossagentmemory migrate -p my-project --from-backend sqlite --to-backend postgres

# Specify custom source DB or target DSN
crossagentmemory migrate --from-db-path ./old.db --to-dsn postgresql://user:pass@host/db
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
git clone https://github.com/Vish150988/crossagentmemory.git
cd crossagentmemory
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT © Open Source Community
