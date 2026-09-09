export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
      ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  session: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  trace: (id: string) => request<TraceResponse>(`/api/traces/${id}`),
  tools: () => request<ToolInfo[]>("/api/tools"),
  skills: () => request<SkillInfo[]>("/api/skills"),
  codingDemo: () => request<CodingDemoSnapshot>("/api/coding-demo"),
  runCodingDemo: () => request<CodingDemoSnapshot>("/api/coding-demo/run", { method: "POST" }),
  run: (body: RunRequest) =>
    request<RunResponse>("/api/agent/run", { method: "POST", body: JSON.stringify(body) }),
};

export type SessionSummary = {
  id: string;
  task: string;
  workspace: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  model: string | null;
  summary: string | null;
  error: string | null;
};

export type SessionDetail = SessionSummary & {
  plan: Record<string, unknown> | null;
  final_answer: string | null;
};

export type TraceEvent = {
  id: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  metadata: Record<string, unknown>;
};

export type TraceResponse = { session_id: string; events: TraceEvent[] };
export type ToolInfo = { name: string; description: string };
export type SkillInfo = { name: string; path: string };

export type CodingDemoPhase = {
  id: string;
  label: string;
  state: "complete" | "detected" | "success" | "pending";
  detail: string;
};

export type CodingDemoToolCall = {
  name: string;
  detail: string;
  success: boolean | null;
};

export type CodingDemoTimelineItem = {
  seq: number;
  type: string;
  label: string;
  phase: string;
  state: "complete" | "detected" | "success" | "failed";
  detail: string;
};

export type CodingDemoSnapshot = {
  schema_version: number;
  mode: string;
  task: string;
  phases: CodingDemoPhase[];
  tool_calls: CodingDemoToolCall[];
  retrieval: {
    count: number;
    query: string;
    paths: string[];
  };
  verification: {
    attempt: number;
    command: string;
    success: boolean;
  }[];
  changed_files: string[];
  timeline: CodingDemoTimelineItem[];
  outcome: {
    status: string;
    trace_id: string;
    final_answer: string;
    modified_files: string[];
    tool_names: string[];
    repository_retrieval_count: number;
    repository_paths: string[];
    verification_attempts: number;
    verification_failures: number;
    test_command: string | null;
    tests_passed: number;
    tests_failed: number;
    test_errors: number;
    verification_success: boolean;
    verification_summary: string;
  };
};

export type RunRequest = {
  task: string;
  workspace?: string;
  model?: string;
  max_iterations?: number;
  auto_verify?: boolean;
};

export type RunResponse = {
  session_id: string;
  task: string;
  workspace: string;
  status: string;
  message: string;
  plan: Record<string, unknown> | null;
  summary: string | null;
  error: string | null;
  created_at: string;
};
