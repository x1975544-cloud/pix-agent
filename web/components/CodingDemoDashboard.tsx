"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Braces,
  CheckCircle2,
  CircleX,
  FileDiff,
  FileSearch,
  FileText,
  FlaskConical,
  GitCommitHorizontal,
  Loader2,
  Play,
  RotateCcw,
  Search,
  TerminalSquare,
  Wrench,
  Zap,
} from "lucide-react";
import { api, type CodingDemoSnapshot } from "@/lib/api";

const phaseMeta: Record<
  string,
  { icon: typeof Activity; iconClass: string; activeClass: string }
> = {
  task: {
    icon: Zap,
    iconClass: "text-signal",
    activeClass: "border-signal/60 bg-signal/10",
  },
  "repository-retrieval": {
    icon: FileSearch,
    iconClass: "text-cyan-300",
    activeClass: "border-cyan-400/50 bg-cyan-400/10",
  },
  "tool-calls": {
    icon: Braces,
    iconClass: "text-amber",
    activeClass: "border-amber/60 bg-amber/10",
  },
  "test-failure": {
    icon: CircleX,
    iconClass: "text-rose-400",
    activeClass: "border-rose-500/60 bg-rose-500/10",
  },
  "autonomous-repair": {
    icon: Wrench,
    iconClass: "text-violet-300",
    activeClass: "border-violet-400/60 bg-violet-400/10",
  },
  "test-success": {
    icon: CheckCircle2,
    iconClass: "text-mint",
    activeClass: "border-mint/60 bg-mint/10",
  },
};

const toolIcon: Record<string, typeof TerminalSquare> = {
  search_code: Search,
  read_file: FileText,
  write_file: FileDiff,
  run_shell: TerminalSquare,
  git_diff: GitCommitHorizontal,
  git_status: GitCommitHorizontal,
  git_commit: GitCommitHorizontal,
};

type DashboardProps = {
  initial: CodingDemoSnapshot | null;
};

function Stat({ label, value, icon: Icon, tone }: {
  label: string;
  value: string | number;
  icon: typeof Activity;
  tone: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-400">{label}</p>
        <Icon size={15} className={tone} />
      </div>
      <p className="mt-2 truncate font-mono text-xl text-white">{value}</p>
    </div>
  );
}

export function CodingDemoDashboard({ initial }: DashboardProps) {
  const [snapshot, setSnapshot] = useState<CodingDemoSnapshot | null>(initial);
  const [visible, setVisible] = useState(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current = [];
  }, []);

  const playTimeline = useCallback(
    (next: CodingDemoSnapshot) => {
      clearTimers();
      setSnapshot(next);
      setError("");
      setVisible(0);
      next.timeline.forEach((_, index) => {
        timers.current.push(
          setTimeout(() => setVisible(index + 1), 360 * (index + 1)),
        );
      });
    },
    [clearTimers],
  );

  useEffect(() => {
    if (initial) {
      const timer = setTimeout(() => playTimeline(initial), 550);
      timers.current.push(timer);
    }
    return clearTimers;
  }, [clearTimers, initial, playTimeline]);

  async function runDemo() {
    setRunning(true);
    setError("");
    try {
      const next = await api.runCodingDemo();
      playTimeline(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Coding demo run failed");
    } finally {
      setRunning(false);
    }
  }

  const reachedRank = useMemo(() => {
    if (!snapshot) return -1;
    const rank = new Map(snapshot.phases.map((phase, index) => [phase.id, index]));
    return snapshot.timeline.slice(0, visible).reduce(
      (max, item) => Math.max(max, rank.get(item.phase) ?? -1),
      -1,
    );
  }, [snapshot, visible]);

  if (!snapshot) {
    return (
      <div className="space-y-6">
        <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-medium text-signal">Engineering Showcase</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
              Autonomous Coding Demo
            </h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-line bg-panel px-3 py-1 font-mono">
              deterministic-scripted
            </span>
          </div>
        </header>

        <section className="rounded-lg border border-dashed border-line bg-panel/40 p-10">
          <div className="mx-auto flex max-w-md flex-col items-center text-center">
            <span className="grid h-12 w-12 place-items-center rounded-lg border border-line bg-ink text-signal">
              <Activity size={22} />
            </span>
            <h2 className="mt-4 text-lg font-semibold text-white">Autonomous Coding Demo</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              A FizzBuzz repository is retrieved, tested, repaired and verified by the single agent loop.
            </p>
            <button
              type="button"
              onClick={runDemo}
              disabled={running}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-signal px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {running ? "Running demo" : "Run demo"}
            </button>
            {error && <p className="mt-3 text-xs text-rose-300">{error}</p>}
          </div>
        </section>
      </div>
    );
  }

  const outcome = snapshot.outcome;
  const complete = visible >= snapshot.timeline.length;
  const rankById = new Map(snapshot.phases.map((phase, index) => [phase.id, index]));

  return (
    <div className="space-y-6">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-signal">Engineering Showcase</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
            Autonomous Coding Demo
          </h1>
          <p className="mt-2 max-w-2xl truncate text-sm text-slate-400">{snapshot.task}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-mint/25 bg-mint/10 px-3 py-1 text-xs font-medium text-mint">
            {outcome.status}
          </span>
          <span className="rounded-full border border-line bg-panel px-3 py-1 font-mono text-[11px] text-slate-400">
            {snapshot.mode}
          </span>
          <button
            type="button"
            onClick={() => playTimeline(snapshot)}
            className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/5 hover:text-white"
          >
            <RotateCcw size={14} />
            Replay
          </button>
          <button
            type="button"
            onClick={runDemo}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-lg bg-signal px-3 py-2 text-xs font-medium text-slate-950 transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? "Running" : "Run demo"}
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Timeline events" value={snapshot.timeline.length} icon={Activity} tone="text-signal" />
        <Stat label="Repository hits" value={snapshot.retrieval.count} icon={FileSearch} tone="text-cyan-300" />
        <Stat label="Tool calls" value={snapshot.tool_calls.length} icon={Braces} tone="text-amber" />
        <Stat label="Tests passed" value={outcome.tests_passed} icon={FlaskConical} tone="text-mint" />
        <Stat label="Changed files" value={snapshot.changed_files.length} icon={FileDiff} tone="text-violet-300" />
        <Stat
          label="Fix loops"
          value={outcome.verification_failures}
          icon={Wrench}
          tone="text-rose-300"
        />
      </div>

      <div className="overflow-x-auto pb-1">
        <div className="flex min-w-[1240px] items-stretch gap-2">
          {snapshot.phases.map((phase, index) => {
            const meta = phaseMeta[phase.id] || phaseMeta.task;
            const Icon = meta.icon;
            const active = index === reachedRank;
            const done = reachedRank >= 0 && index < reachedRank;
            const failedPhase = phase.id === "test-failure";
            let cardClass = "border-line bg-panel";
            let iconClass = meta.iconClass;
            if (active) {
              cardClass = meta.activeClass;
            }
            if (done && failedPhase) {
              cardClass = "border-rose-500/25 bg-rose-500/[0.06]";
            } else if (done) {
              cardClass = "border-line bg-panel";
            }
            if (done && !failedPhase) {
              iconClass = "text-mint";
            }
            return (
              <div key={phase.id} className="flex items-center gap-2">
                <div className={`min-h-[116px] w-[196px] rounded-lg border p-4 transition ${cardClass}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-ink">
                      <Icon size={16} className={iconClass} />
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <p className={`mt-3 text-xs font-semibold ${active ? "text-white" : "text-slate-200"}`}>
                    {phase.label}
                  </p>
                  <p className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-slate-500">
                    {phase.detail}
                  </p>
                </div>
                {index < snapshot.phases.length - 1 && <ArrowRight size={15} className="shrink-0 text-slate-600" />}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-white">Trace / Execution Timeline</h2>
              <p className="mt-0.5 font-mono text-[11px] text-slate-500">{outcome.trace_id}</p>
            </div>
            <span className="rounded-full border border-line bg-ink px-2.5 py-1 font-mono text-[10px] text-slate-400">
              {visible}/{snapshot.timeline.length}
            </span>
          </div>
          <div className="max-h-[540px] overflow-y-auto p-3">
            <ol className="relative space-y-1">
              {snapshot.timeline.slice(0, visible).map((item) => {
                const active = item.seq === visible;
                const Icon =
                  item.state === "failed"
                    ? CircleX
                    : item.state === "success"
                      ? CheckCircle2
                      : Activity;
                const iconClass =
                  item.state === "failed"
                    ? "text-rose-400"
                    : item.state === "success"
                      ? "text-mint"
                      : active
                        ? "text-signal"
                        : "text-slate-500";
                return (
                  <li
                    key={item.seq}
                    className={`flex gap-3 rounded-lg border p-3 transition ${
                      active
                        ? "border-signal/60 bg-signal/10"
                        : "border-transparent hover:bg-white/[0.025]"
                    }`}
                  >
                    <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border border-line bg-ink">
                      <Icon size={14} className={iconClass} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-medium text-slate-200">{item.label}</p>
                        <span className="shrink-0 font-mono text-[10px] text-slate-600">
                          {String(item.seq).padStart(2, "0")}
                        </span>
                      </div>
                      <p className="mt-1 truncate font-mono text-[11px] text-slate-500">{item.detail}</p>
                    </div>
                  </li>
                );
              })}
              {visible === 0 && (
                <li className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-xs text-slate-500">
                  <Activity size={18} className="mx-auto mb-2 text-slate-600" />
                  Trace timeline
                </li>
              )}
            </ol>
          </div>
        </section>

        <aside className="space-y-6">
          <section className="rounded-lg border border-line bg-panel">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3.5">
              <FileDiff size={15} className="text-violet-300" />
              <h2 className="text-sm font-semibold text-white">Changed Files</h2>
            </div>
            <div className="p-3">
              {snapshot.changed_files.length === 0 ? (
                <p className="px-2 py-4 text-xs text-slate-500">No modified files</p>
              ) : (
                snapshot.changed_files.map((file) => (
                  <div key={file} className="flex items-center gap-2 rounded-lg px-2 py-2.5 hover:bg-white/[0.03]">
                    <span className="rounded border border-amber/25 bg-amber/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-amber">
                      M
                    </span>
                    <span className="truncate font-mono text-xs text-slate-300">{file}</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-panel">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3.5">
              <Braces size={15} className="text-amber" />
              <h2 className="text-sm font-semibold text-white">Tool Calls</h2>
            </div>
            <div className="p-3">
              {snapshot.tool_calls.map((call) => {
                const Icon = toolIcon[call.name] || TerminalSquare;
                const ok = call.success === true;
                const failed = call.success === false;
                return (
                  <div key={`${call.name}-${call.detail}`} className="flex items-center gap-3 rounded-lg px-2 py-2.5">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-line bg-ink text-slate-400">
                      <Icon size={14} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-xs text-slate-200">{call.name}</p>
                      <p className="mt-0.5 truncate text-[11px] text-slate-500">{call.detail}</p>
                    </div>
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        ok ? "bg-mint" : failed ? "bg-rose-400" : "bg-slate-600"
                      }`}
                    />
                  </div>
                );
              })}
            </div>
          </section>
        </aside>
      </div>

      {complete && (
        <>
          <section className="rounded-lg border border-line bg-panel p-5">
            <div className="mb-3 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-mint" />
              <h2 className="text-sm font-semibold text-white">Final Answer</h2>
            </div>
            <p className="whitespace-pre-wrap rounded-lg bg-ink p-4 text-sm leading-relaxed text-slate-200">
              {outcome.final_answer}
            </p>
          </section>
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
            <span className="font-mono text-slate-500">{outcome.trace_id}</span>
            <span>{outcome.tests_passed} passed · {outcome.tests_failed} failed · {outcome.test_errors} errors</span>
            <Link
              href={`/traces/${outcome.trace_id}`}
              className="inline-flex items-center gap-1.5 font-medium text-signal hover:text-white"
            >
              Full trace <ArrowRight size={13} />
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
