import { useLiveFeed } from "../hooks/useLiveFeed";
import Badge from "./ui/Badge";
import Card, { CardHeader } from "./ui/Card";
import { SkeletonRow } from "./ui/Skeleton";
import StatusPill from "./ui/StatusPill";

const statusTone = { open: "success", connecting: "warning", closed: "danger" } as const;

function methodTone(method: string) {
  if (method === "GET") return "brand";
  if (method === "DELETE") return "danger";
  return "neutral";
}

export default function LiveFeed({ serviceId }: { serviceId?: number }) {
  const { events, status } = useLiveFeed();
  const shown = (serviceId ? events.filter((e) => e.service_id === serviceId) : events)
    .slice()
    .reverse();

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <span className="text-sm font-medium text-slate-700">Live traffic</span>
        <StatusPill tone={statusTone[status]} pulse={status === "connecting"}>
          {status}
        </StatusPill>
      </CardHeader>
      <ul className="scroll-thin max-h-80 divide-y divide-slate-100 overflow-y-auto text-xs">
        {status === "connecting" && shown.length === 0 && (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        )}
        {status !== "connecting" && shown.length === 0 && (
          <li className="px-4 py-10 text-center text-slate-400">
            Waiting for traffic — hit your gateway URL to see it appear here live.
          </li>
        )}
        {shown.map((e, i) => (
          <li
            key={i}
            className={`flex items-center gap-2.5 px-4 py-2 font-mono ${i === 0 ? "animate-fade-in" : ""}`}
          >
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${e.allowed ? "bg-emerald-500" : "bg-red-500"}`}
              title={e.allowed ? "allowed" : "blocked"}
            />
            <span className={`w-9 shrink-0 ${e.allowed ? "text-slate-500" : "font-semibold text-red-600"}`}>
              {e.status_code}
            </span>
            <Badge tone={methodTone(e.method)}>{e.method}</Badge>
            <span className="flex-1 truncate text-slate-700">{e.path}</span>
            <span className="hidden shrink-0 text-slate-400 sm:inline">{e.client_ip}</span>
            {e.latency_ms != null && (
              <span className="hidden shrink-0 text-slate-400 sm:inline">{e.latency_ms}ms</span>
            )}
            <span className="shrink-0 text-slate-400">{new Date(e.at).toLocaleTimeString()}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
