import { Copy, Database, KeyRound, ShieldCheck, SlidersHorizontal } from "lucide-react";

const rows = [
  { name: "OPENAI_API_KEY", value: "configured via .env", secret: true, icon: KeyRound },
  { name: "PIX_MODEL", value: "gpt-4o-mini", secret: false, icon: SlidersHorizontal },
  { name: "PIX_MAX_ITERATIONS", value: "30", secret: false, icon: SlidersHorizontal },
  { name: "PIX_SHELL_TIMEOUT", value: "60", secret: false, icon: SlidersHorizontal },
  { name: "PIX_DATABASE_URL", value: "sqlite:///./pix-agent.db", secret: false, icon: Database },
];

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <p className="text-sm font-medium text-signal">Configuration</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Settings</h1>
        <p className="mt-2 text-sm text-slate-400">Secrets live only in the environment; the UI never fetches them.</p>
      </header>
      <div className="overflow-hidden rounded-xl border border-line bg-panel">
        {rows.map(({ name, value, secret, icon: Icon }) => (
          <div key={name} className="flex items-center gap-4 border-b border-line/60 px-5 py-4 last:border-0">
            <Icon size={16} className={secret ? "text-amber" : "text-slate-500"} />
            <span className="w-48 font-mono text-sm text-slate-200">{name}</span>
            <span className="flex-1 truncate font-mono text-xs text-slate-500">
              {secret ? "********" : value}
            </span>
            {secret ? <ShieldCheck size={16} className="text-mint" /> : <Copy size={15} className="text-slate-600" />}
          </div>
        ))}
      </div>
    </div>
  );
}
