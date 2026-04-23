/**
 * CrossAgentMemory JavaScript/TypeScript SDK
 *
 * Wraps the REST API for use in Node.js and browser environments.
 *
 * Example:
 * ```ts
 * import { CrossAgentMemoryClient } from "crossagentmemory";
 * const client = new CrossAgentMemoryClient("http://127.0.0.1:8746");
 * const memories = await client.listMemories({ project: "my-app" });
 * ```
 */

import type {
  Memory,
  MemoryListResponse,
  CreateMemoryPayload,
  UpdateMemoryPayload,
  SearchResponse,
  StatsResponse,
  ProjectsResponse,
  SummaryResponse,
  DigestResponse,
  GraphResponse,
  TimelineResponse,
  ClustersResponse,
  ConflictsResponse,
  TagResponse,
  KGResponse,
  KGPathsResponse,
  ResolveConflictsPayload,
  ResolveConflictsResponse,
} from "./types.js";

export interface ClientOptions {
  baseUrl: string;
  headers?: Record<string, string>;
}

export class CrossAgentMemoryClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(baseUrl: string = "http://127.0.0.1:8746", headers?: Record<string, string>) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.headers = {
      "Content-Type": "application/json",
      ...headers,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    params?: Record<string, string | number | undefined>,
    body?: unknown
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (params) {
      const search = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== "") {
          search.set(key, String(value));
        }
      }
      const qs = search.toString();
      if (qs) url += `?${qs}`;
    }

    const init: RequestInit = {
      method,
      headers: this.headers,
    };
    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }

    const response = await fetch(url, init);
    if (!response.ok) {
      const text = await response.text().catch(() => "Unknown error");
      throw new Error(`HTTP ${response.status}: ${text}`);
    }
    return response.json() as Promise<T>;
  }

  // ─── Memories ───

  async listMemories(options?: {
    project?: string;
    category?: string;
    session_id?: string;
    user_id?: string;
    tenant_id?: string;
    at_time?: string;
    limit?: number;
    offset?: number;
  }): Promise<MemoryListResponse> {
    return this.request<MemoryListResponse>("GET", "/api/memories", options);
  }

  async getMemory(id: number): Promise<Memory> {
    return this.request<Memory>("GET", `/api/memories/${id}`);
  }

  async createMemory(payload: CreateMemoryPayload): Promise<{ id: number; status: string }> {
    return this.request<{ id: number; status: string }>("POST", "/api/memories", undefined, payload);
  }

  async updateMemory(id: number, payload: UpdateMemoryPayload): Promise<{ id: number; status: string }> {
    return this.request<{ id: number; status: string }>("PUT", `/api/memories/${id}`, undefined, payload);
  }

  async deleteMemory(id: number): Promise<{ id: number; status: string }> {
    return this.request<{ id: number; status: string }>("DELETE", `/api/memories/${id}`);
  }

  // ─── Search ───

  async search(
    q: string,
    options?: { project?: string; user_id?: string; tenant_id?: string; at_time?: string; limit?: number }
  ): Promise<SearchResponse> {
    return this.request<SearchResponse>("GET", "/api/search", { q, ...options });
  }

  // ─── Projects & Stats ───

  async listProjects(): Promise<ProjectsResponse> {
    return this.request<ProjectsResponse>("GET", "/api/projects");
  }

  async stats(options?: { project?: string; user_id?: string; tenant_id?: string }): Promise<StatsResponse> {
    return this.request<StatsResponse>("GET", "/api/stats", options);
  }

  // ─── Summarization ───

  async summarize(project?: string, llm?: boolean): Promise<SummaryResponse> {
    return this.request<SummaryResponse>("GET", "/api/summarize", { project, llm: llm ? "true" : undefined });
  }

  async digest(project?: string, days?: number): Promise<DigestResponse> {
    return this.request<DigestResponse>("GET", "/api/digest", { project, days });
  }

  // ─── Graph ───

  async getGraph(project?: string, backend?: string): Promise<GraphResponse> {
    return this.request<GraphResponse>("GET", "/api/graph", { project, backend });
  }

  async getTimeline(project?: string, limit?: number): Promise<TimelineResponse> {
    return this.request<TimelineResponse>("GET", "/api/timeline", { project, limit });
  }

  async getClusters(project?: string): Promise<ClustersResponse> {
    return this.request<ClustersResponse>("GET", "/api/clusters", { project });
  }

  // ─── Conflicts ───

  async getConflicts(project?: string): Promise<ConflictsResponse> {
    return this.request<ConflictsResponse>("GET", "/api/conflicts", { project });
  }

  async resolveConflicts(payload?: ResolveConflictsPayload): Promise<ResolveConflictsResponse> {
    return this.request<ResolveConflictsResponse>("POST", "/api/conflicts/resolve", undefined, payload ?? {});
  }

  // ─── Auto-tag ───

  async autoTag(content: string): Promise<TagResponse> {
    return this.request<TagResponse>("POST", "/api/tag", undefined, { content });
  }

  // ─── Knowledge Graph ───

  async getKnowledgeGraph(project?: string): Promise<KGResponse> {
    return this.request<KGResponse>("GET", "/api/kg", { project });
  }

  async getKGPaths(start: string, end: string, project?: string, maxDepth?: number): Promise<KGPathsResponse> {
    return this.request<KGPathsResponse>("GET", "/api/kg/paths", { start, end, project, max_depth: maxDepth });
  }
}
