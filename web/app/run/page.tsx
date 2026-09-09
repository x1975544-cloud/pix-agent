"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Loader2, Play, TerminalSquare } from "lucide-react";
import { api, type RunResponse } from "@/lib/api";

export default function RunPage() {
  const router = useRouter();
  const [task, setTask] = useState("Analyze this repository and report its structure.");
  const [workspace, setWorkspace] = useState("");
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await api.run({
        task,
        workspace: workspace || undefined,
        model: model || undefined,
        auto_verify: true,
      });
      setResult(response);
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Run failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <p className="text-sm font-medium text-signal">Reason · Act · Observe</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Agent Run</h1>
        <p className="mt-2 text-sm text-slate-400">
          The runtime plans, inspects, edits, verifies and commits using real tools.
        </p>
      </header>

      <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-panel p-6">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-300">Task</span>
          <textarea
            value={task}
            onChange={(event) => setTask(event.target.value)}
            rows={4}
            className="w-full resize-none rounded-lg border border-line bg-ink px-3.5 py-3 text-sm text-slate-100 outline-none transition focus:border-signal"
            placeholder="Describe a software engineering task..."
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-300">Workspace (optional)</span>
            <input
              value={workspace}
              onChange={(event) => setWorkspace(event.target.value)}
              className="w-full rounded-lg border border-line bg-ink px-3.5 py-2.5 text-sm outline-none focus:border-signal"
              placeholder="./demo"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-300">Model (optional)</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              className="w-full rounded-lg border border-line bg-ink px-3.5 py-2.5 text-sm outline-none focus:border-signal"
              placeholder="gpt-4o-mini"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading || !task.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-signal px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {loading ? "Running agent..." : "Run agent"}
        </button>
      </form>

      {error && <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-300">{error}</div>}
      {result && (
        <section className="rounded-xl border border-line bg-panel p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-white">Run complete</h2>
            <span className="rounded-full bg-mint/10 px-2.5 py-1 text-xs font-medium text-mint">{result.status}</span>
          </div>
          <p className="font-mono text-xs text-slate-400">{result.session_id}</p>
          <p className="mt-3 whitespace-pre-wrap rounded-lg bg-ink p-4 text-sm leading-relaxed text-slate-200">
            {result.message}
          </p>
          <a href={`/traces/${result.session_id}`} className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-signal">
            <TerminalSquare size={15} /> Open trace
          </a>
        </section>
      )}
    </div>
  );
}
