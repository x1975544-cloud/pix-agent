import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, GitCommitHorizontal, ShieldCheck, TerminalSquare } from "lucide-react";
import { api } from "@/lib/api";
import { TraceTimeline } from "@/components/TraceTimeline";
import { StatusBadge } from "@/components/StatusBadge";

export default async function TracePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let trace;
  let session;
  try {
    [trace, session] = await Promise.all([api.trace(id), api.session(id)]);
  } catch {
    notFound();
  }

  const toolCalls = trace.events.filter((event) => event.type === "TOOL_CALL").length;
  const errors = trace.events.filter((event) => event.type === "AGENT_ERROR").length;

  return (
    <div className="space-y-6">
      <Link href="/sessions" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
        <ArrowLeft size={15} /> Sessions
      </Link>
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="font-mono text-xs text-signal">{trace.session_id}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">{session.task}</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">{session.summary || session.workspace}</p>
        </div>
        <StatusBadge status={session.status} />
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-line bg-panel p-5">
          <div className="flex items-center gap-2 text-sm text-slate-400"><TerminalSquare size={15} className="text-signal" /> Tool calls</div>
          <p className="mt-2 text-2xl font-semibold text-white">{toolCalls}</p>
        </div>
        <div className="rounded-xl border border-line bg-panel p-5">
          <div className="flex items-center gap-2 text-sm text-slate-400"><ShieldCheck size={15} className="text-mint" /> Errors</div>
          <p className="mt-2 text-2xl font-semibold text-white">{errors}</p>
        </div>
        <div className="rounded-xl border border-line bg-panel p-5">
          <div className="flex items-center gap-2 text-sm text-slate-400"><GitCommitHorizontal size={15} className="text-amber" /> Git safety</div>
          <p className="mt-2 text-2xl font-semibold text-white">Sandboxed</p>
        </div>
      </div>

      <section className="rounded-xl border border-line bg-panel">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Event timeline</h2>
          <p className="mt-0.5 text-xs text-slate-500">Redacted, persisted and ordered by timestamp.</p>
        </div>
        <div className="p-4">
          <TraceTimeline events={trace.events} />
        </div>
      </section>

      {session.final_answer && (
        <section className="rounded-xl border border-line bg-panel p-5">
          <h2 className="mb-3 text-sm font-semibold text-white">Final answer</h2>
          <p className="whitespace-pre-wrap rounded-lg bg-ink p-4 text-sm leading-relaxed text-slate-200">
            {session.final_answer}
          </p>
        </section>
      )}
    </div>
  );
}
