import Link from "next/link";
import { Activity, ExternalLink } from "lucide-react";
import { api, type SessionSummary } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default async function SessionsPage() {
  let sessions: SessionSummary[] = [];
  let error: string | null = null;
  try {
    sessions = await api.sessions();
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "API unavailable";
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm font-medium text-signal">Persistence</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Sessions</h1>
      </header>
      {error ? (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-300">{error}</div>
      ) : (
        <section className="overflow-hidden rounded-xl border border-line bg-panel">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center px-6 py-16 text-center">
              <Activity size={28} className="mb-3 text-slate-600" />
              <p className="text-sm text-slate-400">No sessions recorded.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="border-b border-line text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-5 py-3 font-medium">Session</th>
                    <th className="px-5 py-3 font-medium">Task</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Model</th>
                    <th className="px-5 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.id} className="border-b border-line/40 last:border-0 hover:bg-white/[0.03]">
                      <td className="px-5 py-3.5 font-mono text-xs text-signal">{session.id}</td>
                      <td className="max-w-[340px] truncate px-5 py-3.5 text-slate-200">{session.task}</td>
                      <td className="px-5 py-3.5"><StatusBadge status={session.status} /></td>
                      <td className="px-5 py-3.5 text-slate-400">{session.model || "default"}</td>
                      <td className="px-5 py-3.5 text-right">
                        <Link href={`/traces/${session.id}`} className="inline-flex items-center gap-1 text-xs font-medium text-slate-300 hover:text-white">
                          Trace <ExternalLink size={13} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
