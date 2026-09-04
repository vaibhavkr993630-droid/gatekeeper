import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type Algorithm, servicesApi } from "../api";
import LiveFeed from "./LiveFeed";
import UsageCharts from "./UsageCharts";

const ALGORITHMS: Algorithm[] = ["sliding_window_counter", "token_bucket"];

export default function ServicesPanel() {
  const qc = useQueryClient();
  const { data: services = [], isLoading } = useQuery({
    queryKey: ["services"],
    queryFn: servicesApi.list,
  });

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [algorithm, setAlgorithm] = useState<Algorithm>("sliding_window_counter");
  const [limit, setLimit] = useState(100);
  const [windowSeconds, setWindowSeconds] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const create = useMutation({
    mutationFn: () =>
      servicesApi.create({
        name,
        upstream_url: url,
        rule: { algorithm, limit, window_seconds: windowSeconds, burst: null },
      }),
    onSuccess: () => {
      setName("");
      setUrl("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["services"] });
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const remove = useMutation({
    mutationFn: servicesApi.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["services"] }),
  });

  const mintKey = useMutation({
    mutationFn: (id: number) => servicesApi.createKey(id, "dashboard"),
    onSuccess: (k) => setNewKey(k.api_key),
  });

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Services</h1>
        <p className="text-sm text-slate-500">
          Register a backend and its rate-limit policy. You'll route traffic through the
          gateway endpoint (Phase 4).
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="grid grid-cols-2 gap-3 rounded-lg border bg-white p-4"
      >
        <input
          className="rounded border p-2 text-sm"
          placeholder="Service name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="rounded border p-2 text-sm"
          placeholder="https://your-backend.example.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <select
          className="rounded border p-2 text-sm"
          value={algorithm}
          onChange={(e) => setAlgorithm(e.target.value as Algorithm)}
        >
          {ALGORITHMS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <div className="flex gap-2">
          <input
            type="number"
            className="w-full rounded border p-2 text-sm"
            value={limit}
            min={1}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
          <span className="self-center text-sm text-slate-400">per</span>
          <input
            type="number"
            className="w-full rounded border p-2 text-sm"
            value={windowSeconds}
            min={1}
            onChange={(e) => setWindowSeconds(Number(e.target.value))}
          />
          <span className="self-center text-sm text-slate-400">s</span>
        </div>
        {error && <p className="col-span-2 text-sm text-red-600">{error}</p>}
        <button
          className="col-span-2 rounded bg-slate-900 p-2 text-sm text-white disabled:opacity-50"
          disabled={create.isPending}
        >
          Add service
        </button>
      </form>

      {newKey && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
          <p className="font-medium">Copy this API key now — it won't be shown again:</p>
          <code className="mt-1 block break-all rounded bg-white p-2">{newKey}</code>
          <button className="mt-2 text-xs underline" onClick={() => setNewKey(null)}>
            Dismiss
          </button>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : services.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-white p-10 text-center text-sm text-slate-400">
          No services yet.
        </div>
      ) : (
        <ul className="space-y-2">
          {services.map((s) => (
            <li key={s.id} className="rounded-lg border bg-white p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">
                  {s.name} {!s.is_active && <span className="text-slate-400">(inactive)</span>}
                </span>
                <div className="flex gap-3">
                  <button
                    className="text-slate-500 underline"
                    onClick={() => setOpenId(openId === s.id ? null : s.id)}
                  >
                    {openId === s.id ? "Hide" : "Dashboard"}
                  </button>
                  <button className="text-slate-500 underline" onClick={() => mintKey.mutate(s.id)}>
                    New API key
                  </button>
                  <button className="text-red-600 underline" onClick={() => remove.mutate(s.id)}>
                    Delete
                  </button>
                </div>
              </div>
              <p className="mt-1 text-slate-500">
                → {s.upstream_url} · {s.rule.algorithm} {s.rule.limit}/{s.rule.window_seconds}s
              </p>
              <p className="mt-1 font-mono text-xs text-slate-400">gw id: {s.public_id}</p>
              {openId === s.id && (
                <div className="mt-4 grid gap-4 border-t pt-4 lg:grid-cols-2">
                  <UsageCharts serviceId={s.id} />
                  <LiveFeed serviceId={s.id} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
