# CrossAgentMemory JS/TS SDK

Node.js / browser client for [CrossAgentMemory](https://github.com/Vish150988/crossagentmemory).

## Install

```bash
npm install crossagentmemory
# or
yarn add crossagentmemory
# or
pnpm add crossagentmemory
```

## Quick Start

```typescript
import { CrossAgentMemoryClient } from "crossagentmemory";

const client = new CrossAgentMemoryClient("http://127.0.0.1:8746");

// Capture a memory
await client.createMemory({
  project: "my-app",
  content: "Chose Zustand over Redux for state management",
  category: "decision",
  confidence: 0.95,
});

// Search memories
const results = await client.search("state management", { project: "my-app" });
console.log(results.results);

// Get knowledge graph
const graph = await client.getKnowledgeGraph("my-app");
console.log(graph.nodes, graph.edges);

// Auto-resolve conflicts
await client.resolveConflicts({ project: "my-app", strategy: "decay" });
```

## API

### Memories
- `listMemories(options?)` — List memories with filtering
- `getMemory(id)` — Get single memory
- `createMemory(payload)` — Create a memory
- `updateMemory(id, payload)` — Update a memory
- `deleteMemory(id)` — Delete a memory

### Search & Discovery
- `search(q, options?)` — Keyword search
- `autoTag(content)` — Auto-generate tags

### Projects
- `listProjects()` — List all projects
- `stats(options?)` — Get statistics
- `summarize(project?, llm?)` — Generate summary
- `digest(project?, days?)` — Weekly digest

### Graph & Visualization
- `getGraph(project?, backend?)` — Similarity graph
- `getTimeline(project?, limit?)` — Timeline view
- `getClusters(project?)` — Category clusters
- `getKnowledgeGraph(project?)` — Entity-relationship graph
- `getKGPaths(start, end, project?, maxDepth?)` — Find paths between entities

### Conflicts
- `getConflicts(project?)` — Detect contradictions
- `resolveConflicts(payload?)` — Auto-resolve conflicts

## License

MIT
