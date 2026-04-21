# AgentMemory VS Code Extension

Capture and recall AI agent memories directly from VS Code.

## Features

- **Capture Memory** — Select text or type a memory, choose category, store it
- **Recall Memories** — Browse all memories in a webview panel
- **Search** — Find memories by keyword
- **Load Context** — Copy context brief to clipboard for pasting into Claude/Cursor
- **Sync CLAUDE.md** — Generate/update CLAUDE.md from memories
- **Auto-capture** — Optional: capture on every file save

## Requirements

- AgentMemory CLI installed: `pip install agentmemory`

## Usage

Open Command Palette (`Ctrl+Shift+P`) and type:

- `AgentMemory: Capture Memory`
- `AgentMemory: Recall Memories`
- `AgentMemory: Search Memories`
- `AgentMemory: Load Context Brief`
- `AgentMemory: Sync CLAUDE.md`

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `agentmemory.project` | `""` | Project name (auto-detected from workspace if empty) |
| `agentmemory.autoCapture` | `false` | Auto-capture on file save |

## Install from Source

```bash
cd vscode-extension
npm install
npm run compile
# Press F5 in VS Code to launch extension host
```
