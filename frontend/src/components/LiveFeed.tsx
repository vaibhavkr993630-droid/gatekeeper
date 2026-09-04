import { useLiveFeed } from "../hooks/useLiveFeed";

export default function LiveFeed({ serviceId }: { serviceId?: number }) {
  const { events, status } = useLiveFeed();
  const shown = (serviceId ? events.filter((e) => e.service_id === serviceId) : events)
    .slice()
    .reverse();

  return (
    <div className="rounded-lg border bg-white">
      <div className="flex items-center justify-between border-b px-4 py-2 text-sm">
        <span className="font-medium">Live traffic</span>
        <span
          className={
            status === "open"
              ? "text-emerald-600"
              : status === "connecting"
                ? "text-amber-600"
                : "text-red-600"
          }
        >
          ● {status}
        </span>
      </div>
      <ul className="max-h-80 divide-y overflow-y-auto text-xs">
        {shown.length === 0 && (
          <li className="p-4 text-center text-slate-400">Waiting for traffic…</li>
        )}
        {shown.map((e, i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-1.5 font-mono">
            <span
              className={e.allowed ? "text-emerald-600" : "text-red-600"}
              title={e.allowed ? "allowed" : "blocked"}
            >
              {e.allowed ? "✔" : "✖"}
            </span>
            <span className="w-10 text-slate-500">{e.status_code}</span>
            <span className="w-12 text-slate-700">{e.method}</span>
            <span className="flex-1 truncate">{e.path}</span>
            <span className="text-slate-400">{e.client_ip}</span>
            {e.latency_ms != null && <span className="text-slate-400">{e.latency_ms}ms</span>}
            <span className="text-slate-400">
              {new Date(e.at).toLocaleTimeString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
