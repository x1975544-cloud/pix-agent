import Link from "next/link";
import { Activity, ArrowRight, Braces, CheckCircle2, Play, TerminalSquare } from "lucide-react";
import { api, type SessionSummary } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function DashboardPage() {
  let sessions: SessionSummary[] = [];
  let toolCount = 0;
  let error: string | null = null;
  try {
    [sessions, toolCount] = await Promise.all([api.sessions(), api.tools().then((tools) => tools.length)]);
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "API unavailable";
  }

  const succeeded = sessions.filter((session) => session.status === "success").length;
  return (
    <div className="space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-signal">Agent Runtime</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
            Inspect real sessions, traces, tools and verification output from the PiX backend.
          </p>
        </div>
        <Link
          href="/run"
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-signal px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-blue-400"
        >
          <Play size={16} />
          New Agent Run
        </Link>
      </header>

      {error ? (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 p-5 text-sm text-rose-300">
          Backend is not reachable at the configured API URL. Start it with <code>uv run pix serve</code>.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "Sessions", value: sessions.length, icon: Activity, tone: "text-signal" },
            { label: "Succeeded", value: succeeded, icon: CheckCircle2, tone: "text-mint" },
            { label: "Available Tools", value: toolCount, icon: Braces, tone: "text-amber" },
          ].map(({ label, value, icon: Icon, tone }) => (
            <div key={label} className="rounded-xl border border-line bg-panel p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">{label}</p>
                <Icon size={17} className={tone} />
              </div>
              <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      <section className="rounded-xl border border-line bg-panel">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Recent Sessions</h2>
            <p className="mt-0.5 text-xs text-slate-500">Persisted by the SQLite session store.</p>
          </div>
          <Link href="/sessions" className="inline-flex items-center gap-1.5 text-xs font-medium text-signal">
            View all <ArrowRight size={14} />
          </Link>
        </div>
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center px-6 py-14 text-center">
            <TerminalSquare size={28} className="mb-3 text-slate-600" />
            <p className="text-sm text-slate-400">No sessions yet.</p>
            <Link href="/run" className="mt-4 rounded-lg border border-line px-4 py-2 text-xs text-slate-300 hover:bg-white/5">
              Start one now
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr className="border-b border-line/70">
                  <th className="px-5 py-3 font-medium">Task</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Workspace</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 6).map((session) => (
                  <tr key={session.id} className="border-b border-line/40 last:border-0 hover:bg-white/[0.03]">
                    <td className="max-w-[340px] truncate px-5 py-3.5 text-slate-200">{session.task}</td>
                    <td className="px-5 py-3.5"><StatusBadge status={session.status} /></td>
                    <td className="max-w-[220px] truncate px-5 py-3.5 font-mono text-xs text-slate-400">
                      {session.workspace}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400">{formatDate(session.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
