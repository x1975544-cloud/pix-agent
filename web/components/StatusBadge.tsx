export function StatusBadge({ status }: { status: string }) {
  const palette: Record<string, string> = {
    success: "bg-mint/10 text-mint border-mint/25",
    running: "bg-signal/10 text-signal border-signal/25",
    pending: "bg-amber/10 text-amber border-amber/25",
    failed: "bg-rose-500/10 text-rose-400 border-rose-500/25",
    cancelled: "bg-slate-500/10 text-slate-300 border-slate-400/25",
  };
  const className = palette[status] || palette.pending;
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      {status}
    </span>
  );
}
