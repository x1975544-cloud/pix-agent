import { FlaskConical, Info } from "lucide-react";

const categories = ["repository_navigation", "bug_fixing", "test_generation", "refactoring", "feature_implementation"];

export default function BenchmarkPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm font-medium text-signal">Evaluation</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Benchmark</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Real task runs with machine-checkable validation. No fabricated scores are shown.
        </p>
      </header>
      <div className="flex gap-3 rounded-xl border border-amber/25 bg-amber/10 p-4 text-sm text-amber">
        <Info size={17} className="shrink-0" />
        Run <code className="font-mono">uv run pix benchmark benchmarks/tasks</code> with an API key to generate results.
      </div>
      <div className="overflow-hidden rounded-xl border border-line bg-panel">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Task categories</h2>
        </div>
        <div className="grid gap-px bg-line/60 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((category, index) => (
            <div key={category} className="bg-panel p-5">
              <FlaskConical size={16} className="mb-3 text-mint" />
              <p className="font-mono text-sm text-slate-200">{String(index + 1).padStart(2, "0")} / {category}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
