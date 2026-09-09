"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Braces,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Play,
  Settings,
  Zap,
} from "lucide-react";

const items = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/run", label: "Agent Run", icon: Play },
  { href: "/sessions", label: "Sessions", icon: Activity },
  { href: "/tools", label: "Tools", icon: Braces },
  { href: "/benchmark", label: "Benchmark", icon: FlaskConical },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-line bg-panel/90 backdrop-blur lg:block">
      <div className="flex h-full flex-col px-5 py-6">
        <Link href="/" className="mb-8 flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-signal/15 text-signal">
            <Zap size={20} />
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-wide text-white">PiX Agent</span>
            <span className="block text-[11px] text-slate-400">Plan · Act · Verify · Commit</span>
          </span>
        </Link>

        <nav className="space-y-1">
          {items.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                  active
                    ? "bg-signal/15 font-medium text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                <Icon size={17} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl border border-line bg-white/[0.03] p-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-300">
            <Gauge size={14} className="text-mint" />
            Runtime
          </div>
          <p className="text-xs leading-relaxed text-slate-500">
            Python agent runtime with SQLite traces, sandboxed tools and an
            OpenAI-compatible provider interface.
          </p>
        </div>
      </div>
    </aside>
  );
}
