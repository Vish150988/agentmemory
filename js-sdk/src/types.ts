export interface Memory {
  id: number;
  project: string;
  session_id: string;
  timestamp: string;
  category: "fact" | "decision" | "action" | "preference" | "error";
  content: string;
  confidence: number;
  source: string;
  tags: string;
  user_id?: string;
  tenant_id?: string;
  valid_from?: string;
  valid_until?: string;
}

export interface CreateMemoryPayload {
  project?: string;
  content: string;
  category?: string;
  confidence?: number;
  source?: string;
  tags?: string;
  user_id?: string;
  tenant_id?: string;
  valid_from?: string;
  valid_until?: string;
}

export interface UpdateMemoryPayload {
  content?: string;
  category?: string;
  confidence?: number;
  tags?: string;
  user_id?: string;
  tenant_id?: string;
  valid_from?: string;
  valid_until?: string;
}

export interface MemoryListResponse {
  total: number;
  offset: number;
  memories: Memory[];
}

export interface SearchResponse {
  query: string;
  results: Memory[];
}

export interface StatsResponse {
  total_memories: number;
  projects: number;
  sessions: number;
  by_category: Record<string, number>;
  project_memories?: number;
}

export interface ProjectsResponse {
  projects: string[];
}

export interface SummaryResponse {
  project: string;
  summary: string;
}

export interface DigestResponse {
  project: string;
  days: number;
  digest: string;
}

export interface GraphNode {
  id: number;
  content: string;
  category: string;
  confidence: number;
}

export interface GraphEdge {
  source: number;
  target: number;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineItem {
  id: number;
  content: string;
  category: string;
  timestamp: string;
  confidence: number;
}

export interface TimelineResponse {
  timeline: TimelineItem[];
}

export interface ClustersResponse {
  [category: string]: Array<{ id: number; content: string; confidence: number }>;
}

export interface Conflict {
  a: number;
  b: number;
  reason: string;
}

export interface ConflictsResponse {
  project: string;
  conflicts: Conflict[];
}

export interface TagResponse {
  content: string;
  tags: string[];
}

export interface KGNode {
  id: number;
  name: string;
  type: string;
  created_at: string;
}

export interface KGEdge {
  id: number;
  source: number;
  target: number;
  relation: string;
  weight: number;
  memory_id?: number;
}

export interface KGResponse {
  nodes: KGNode[];
  edges: KGEdge[];
}

export interface KGPathsResponse {
  paths: Array<Array<{ source: number; target: number; relation: string; weight: number }>>;
}

export interface ResolveConflictsPayload {
  project?: string;
  strategy?: "decay" | "expire" | "both";
  decay_amount?: number;
}

export interface ResolveConflictsResponse {
  resolved: number;
  actions: Array<{
    memory_id: number;
    reason: string;
    strategy: string;
    changes: Record<string, unknown>;
  }>;
}
