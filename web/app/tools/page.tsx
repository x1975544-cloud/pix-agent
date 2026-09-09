import { Braces, ShieldCheck, TerminalSquare } from "lucide-react";
import { api, type ToolInfo } from "@/lib/api";

export default async function ToolsPage() {
  let tools: ToolInfo[] = [];
  let error: string | null = null;
  try {
    tools = await api.tools();
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "API unavailable";
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm font-medium text-signal">Tool Registry</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Tools</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Local tools plus MCP adapters share one provider-neutral interface.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-line bg-panel p-4 text-sm">
          <Braces size={16} className="mb-2 text-signal" /> JSON schemas sent to the model
        </div>
        <div className="rounded-xl border border-line bg-panel p-4 text-sm">
          <TerminalSquare size={16} className="mb-2 text-amber" /> Workspace-scoped execution
        </div>
        <div className="rounded-xl border border-line bg-panel p-4 text-sm">
          <ShieldCheck size={16} className="mb-2 text-mint" /> Path and command validation
        </div>
      </div>
      {error ? (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-300">{error}</div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {tools.map((tool) => (
            <div key={tool.name} className="rounded-xl border border-line bg-panel p-4">
              <p className="font-mono text-sm font-medium text-mint">{tool.name}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{tool.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
