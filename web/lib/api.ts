export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
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
