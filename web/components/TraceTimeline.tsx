"use client";

import { useMemo } from "react";
import { Activity, Braces, Check, CircleAlert, FileSearch, GitCommitHorizontal, Play, Sparkles } from "lucide-react";
import type { TraceEvent } from "@/lib/api";

const typeMeta: Record<string, { label: string; icon: typeof Activity; tone: string }> = {
  SESSION_STARTED: { label: "Session started", icon: Play, tone: "text-signal" },
  REPOSITORY_ANALYZED: { label: "Repository analyzed", icon: FileSearch, tone: "text-cyan-400" },
  PLAN_CREATED: { label: "Plan created", icon: Sparkles, tone: "text-violet-400" },
  LLM_REQUEST: { label: "LLM request", icon: Sparkles, tone: "text-amber" },
  LLM_RESPONSE: { label: "LLM response", icon: Sparkles, tone: "text-amber" },
  TOOL_CALL: { label: "Tool call", icon: Braces, tone: "text-slate-300" },
  TOOL_RESULT: { label: "Tool result", icon: Check, tone: "text-mint" },
  VERIFICATION_STARTED: { label: "Verification started", icon: Activity, tone: "text-lime-400" },
  VERIFICATION_FINISHED: { label: "Verification finished", icon: Check, tone: "text-lime-400" },
  GIT_OPERATION: { label: "Git operation", icon: GitCommitHorizontal, tone: "text-orange-300" },
  AGENT_ERROR: { label: "Agent error", icon: CircleAlert, tone: "text-rose-400" },
  AGENT_FINISHED: { label: "Agent finished", icon: Check, tone: "text-mint" },
};

function summary(event: TraceEvent) {
  const payload = event.payload || {};
  if (payload.name) return String(payload.name);
  if (payload.command) return String(payload.command);
  if (payload.task) return String(payload.task);
  if (payload.status) return String(payload.status);
  if (payload.title) return String(payload.title);
  if (payload.success !== undefined) return String(payload.success);
  return "";
}

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  const filtered = useMemo(() => {
    const compact: Record<string, TraceEvent> = {};
    for (const event of events) {
      if (!compact[event.type] || event.type === "TOOL_CALL" || event.type === "LLM_REQUEST") {
        compact[event.type] = event;
      }
    }
    return events.filter((event) => {
      if (event.type === "ITERATION_STARTED") return false;
      if (event.type === "TOOL_CALL" || event.type === "LLM_REQUEST") return true;
      return !compact[event.type] || event.type === "TOOL_RESULT" || event.type === "LLM_RESPONSE";
    });
  }, [events]);

  return (
    <div className="relative space-y-1">
      {filtered.map((event) => {
        const meta = typeMeta[event.type] || { label: event.type.replaceAll("_", " "), icon: Activity, tone: "text-slate-400" };
        const Icon = meta.icon;
        return (
          <div key={event.id} className="relative flex gap-4 rounded-lg px-3 py-2.5 hover:bg-white/[0.03]">
            <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-ink">
              <Icon size={15} className={meta.tone} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-200">{meta.label}</p>
                <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
                  {event.duration_ms !== null && <span>{event.duration_ms} ms</span>}
                  <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
              {summary(event) && (
                <p className="mt-1 truncate font-mono text-xs text-slate-500">{summary(event)}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
