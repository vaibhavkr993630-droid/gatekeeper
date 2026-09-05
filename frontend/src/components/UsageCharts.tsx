import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { servicesApi } from "../api";
import StatTile from "./ui/StatTile";
import { SkeletonCard } from "./ui/Skeleton";

const tick = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function UsageCharts({ serviceId }: { serviceId: number }) {
  const { data } = useQuery({
    queryKey: ["stats", serviceId],
    queryFn: () => servicesApi.stats(serviceId, 60),
    refetchInterval: 5000,
  });

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const series = data.series.map((p) => ({
    ...p,
    allowed: p.requests - p.blocked,
    t: tick(p.minute),
  }));
  const { requests, blocked, block_rate } = data.totals;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <StatTile label="requests / 60m" value={requests} />
        <StatTile label="blocked" value={blocked} tone={blocked ? "danger" : "default"} />
        <StatTile label="block rate" value={`${(block_rate * 100).toFixed(1)}%`} />
      </div>

      <ChartCard title="Requests per minute">
        <AreaChart data={series}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="t" fontSize={11} />
          <YAxis fontSize={11} allowDecimals={false} width={28} />
          <Tooltip />
          <Area type="monotone" dataKey="allowed" stackId="1" stroke="#059669" fill="#a7f3d0" />
          <Area type="monotone" dataKey="blocked" stackId="1" stroke="#dc2626" fill="#fecaca" />
        </AreaChart>
      </ChartCard>

      <ChartCard title="Blocked per minute">
        <BarChart data={series}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="t" fontSize={11} />
          <YAxis fontSize={11} allowDecimals={false} width={28} />
          <Tooltip />
          <Bar dataKey="blocked" fill="#dc2626" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ChartCard>

      <p className="text-xs text-slate-400">
        Policy: {data.rule.algorithm} · {data.rule.limit} req / {data.rule.window_seconds}s per
        client IP
      </p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-card">
      <div className="mb-2 text-sm font-medium text-slate-700">{title}</div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
