import { describe, it, expect, beforeAll } from "vitest";
import { CrossAgentMemoryClient } from "../src/client.js";

const client = new CrossAgentMemoryClient("http://127.0.0.1:8746");

describe("CrossAgentMemoryClient", () => {
  // These tests assume a local server is running on :8746.
  // Start it with: crossagentmemory server

  it("creates and retrieves a memory", async () => {
    const created = await client.createMemory({
      project: "sdk-test",
      content: "SDK integration test memory",
      category: "fact",
      confidence: 0.95,
    });
    expect(created.status).toBe("created");
    expect(typeof created.id).toBe("number");

    const memory = await client.getMemory(created.id);
    expect(memory.content).toBe("SDK integration test memory");
    expect(memory.category).toBe("fact");
  });

  it("lists memories for a project", async () => {
    const list = await client.listMemories({ project: "sdk-test", limit: 10 });
    expect(Array.isArray(list.memories)).toBe(true);
    expect(list.memories.length).toBeGreaterThan(0);
  });

  it("searches memories", async () => {
    const results = await client.search("SDK", { project: "sdk-test" });
    expect(Array.isArray(results.results)).toBe(true);
  });

  it("gets projects", async () => {
    const projects = await client.listProjects();
    expect(Array.isArray(projects.projects)).toBe(true);
    expect(projects.projects.includes("sdk-test")).toBe(true);
  });

  it("gets stats", async () => {
    const stats = await client.stats({ project: "sdk-test" });
    expect(typeof stats.total_memories).toBe("number");
    expect(typeof stats.projects).toBe("number");
  });

  it("auto-tags content", async () => {
    const result = await client.autoTag("auth system with JWT tokens");
    expect(Array.isArray(result.tags)).toBe(true);
    expect(result.content).toBe("auth system with JWT tokens");
  });

  it("gets conflicts", async () => {
    const conflicts = await client.getConflicts("sdk-test");
    expect(Array.isArray(conflicts.conflicts)).toBe(true);
  });

  it("gets graph", async () => {
    const graph = await client.getGraph("sdk-test");
    expect(Array.isArray(graph.nodes)).toBe(true);
    expect(Array.isArray(graph.edges)).toBe(true);
  });

  it("updates a memory", async () => {
    const created = await client.createMemory({
      project: "sdk-test",
      content: "To be updated",
    });
    const updated = await client.updateMemory(created.id, { content: "Updated content" });
    expect(updated.status).toBe("updated");

    const memory = await client.getMemory(created.id);
    expect(memory.content).toBe("Updated content");
  });

  it("deletes a memory", async () => {
    const created = await client.createMemory({
      project: "sdk-test",
      content: "To be deleted",
    });
    const deleted = await client.deleteMemory(created.id);
    expect(deleted.status).toBe("deleted");
  });
});
