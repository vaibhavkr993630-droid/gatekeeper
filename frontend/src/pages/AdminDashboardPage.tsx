import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { adminApi, clearAdminToken } from "../api";
import AppShell from "../components/AppShell";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import StatTile from "../components/ui/StatTile";
import StatusPill from "../components/ui/StatusPill";

const tick = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function AdminDashboardPage() {
  const navigate = useNavigate();
  const { data: me } = useQuery({ queryKey: ["admin-me"], queryFn: adminApi.me });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-overview"],
    queryFn: adminApi.overview,
    refetchInterval: 10_000,
  });

  function logout() {
    clearAdminToken();
    navigate("/admin/login");
  }

  if (isError) {
    clearAdminToken();
    navigate("/admin/login");
    return null;
  }

  return (
    <AppShell admin subtitle="System overview" identity={me?.email} onLogout={logout}>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Platform health</h1>
          <p className="text-sm text-slate-400">
            Aggregate, system-wide metrics — no individual tenant traffic is shown here.
          </p>
        </div>
        {data && (
          <div className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white px-3 py-2">
            <StatusPill tone={data.db_ok ? "success" : "danger"} pulse={!data.db_ok}>
              Postgres {data.db_ok ? "OK" : "down"}
            </StatusPill>
            <div className="h-3 w-px bg-slate-200" />
            <StatusPill tone={data.redis_ok ? "success" : "danger"} pulse={!data.redis_ok}>
              Redis {data.redis_ok ? "OK" : "down"}
            </StatusPill>
          </div>
        )}
      </div>

      {isLoading || !data ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <StatTile label="Tenants" value={data.tenants_total} />
            <StatTile label="Services" value={data.services_total} />
            <StatTile label="Requests (24h)" value={data.requests_24h.toLocaleString()} />
            <StatTile
              label="Blocked (24h)"
              value={data.blocked_24h.toLocaleString()}
              tone={data.blocked_24h > 0 ? "danger" : "default"}
            />
            <StatTile
              label="Error rate (24h)"
              value={`${(data.error_rate_24h * 100).toFixed(1)}%`}
              tone={data.error_rate_24h > 0.05 ? "danger" : "default"}
            />
            <StatTile
              label="Avg latency"
              value={data.avg_latency_ms_24h != null ? `${Math.round(data.avg_latency_ms_24h)}ms` : "—"}
            />
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-card">
            <div className="mb-2 text-sm font-medium text-slate-700">
              Platform requests — last 60 minutes
            </div>
            {data.requests_series_60m.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">No traffic in this window.</p>
            ) : (
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={data.requests_series_60m.map((p) => ({
                      ...p,
                      allowed: p.requests - p.blocked,
                      t: tick(p.minute),
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis dataKey="t" fontSize={11} />
                    <YAxis fontSize={11} allowDecimals={false} width={32} />
                    <Tooltip />
                    <Area type="monotone" dataKey="allowed" stackId="1" stroke="#4f46e5" fill="#e0e7ff" />
                    <Area type="monotone" dataKey="blocked" stackId="1" stroke="#dc2626" fill="#fecaca" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-white shadow-card">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-medium text-slate-700">
              Tenants near or over their plan limit
            </div>
            {data.tenants_near_limit.length === 0 ? (
              <EmptyState
                title="Everyone's comfortably within quota"
                description="Tenants using 80%+ of their daily plan limit will show up here."
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.tenants_near_limit.map((t) => (
                  <li key={t.tenant_id} className="flex items-center gap-4 px-4 py-3">
                    <div className="w-40 truncate text-sm font-medium text-slate-800">{t.name}</div>
                    <Badge tone="neutral">{t.plan}</Badge>
                    <div className="flex-1">
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${t.pct_used >= 1 ? "bg-red-500" : "bg-amber-500"}`}
                          style={{ width: `${Math.min(100, t.pct_used * 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-32 text-right text-xs tabular-nums text-slate-500">
                      {t.requests_24h.toLocaleString()} / {t.daily_limit.toLocaleString()}
                    </div>
                    <Badge tone={t.pct_used >= 1 ? "danger" : "warning"}>
                      {(t.pct_used * 100).toFixed(0)}%
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}
