import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, type Algorithm, type Service, servicesApi } from "../api";
import LiveFeed from "./LiveFeed";
import UsageCharts from "./UsageCharts";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import Card, { CardBody, CardHeader } from "./ui/Card";
import CopyButton from "./ui/CopyButton";
import EmptyState from "./ui/EmptyState";
import { SkeletonCard } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";

const ALGORITHMS: { value: Algorithm; label: string }[] = [
  { value: "sliding_window_counter", label: "Sliding window counter" },
  { value: "token_bucket", label: "Token bucket" },
];

const algoLabel = (a: Algorithm) => ALGORITHMS.find((o) => o.value === a)?.label ?? a;

export default function ServicesPanel() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: services = [], isLoading } = useQuery({
    queryKey: ["services"],
    queryFn: servicesApi.list,
  });

  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [algorithm, setAlgorithm] = useState<Algorithm>("sliding_window_counter");
  const [limit, setLimit] = useState(100);
  const [windowSeconds, setWindowSeconds] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<{ serviceName: string; key: string } | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const create = useMutation({
    mutationFn: () =>
      servicesApi.create({
        name,
        upstream_url: url,
        rule: { algorithm, limit, window_seconds: windowSeconds, burst: null },
      }),
    onSuccess: (s) => {
      setName("");
      setUrl("");
      setError(null);
      setFormOpen(false);
      qc.invalidateQueries({ queryKey: ["services"] });
      toast(`Service "${s.name}" created`, "success");
    },
    onError: (e: unknown) => setError(e instanceof ApiError ? e.message : "Failed to create service"),
  });

  const remove = useMutation({
    mutationFn: servicesApi.remove,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services"] });
      setConfirmDeleteId(null);
      toast("Service deleted", "info");
    },
    onError: () => toast("Failed to delete service", "danger"),
  });

  const mintKey = useMutation({
    mutationFn: (s: Service) => servicesApi.createKey(s.id, "dashboard").then((k) => ({ s, k })),
    onSuccess: ({ s, k }) => setNewKey({ serviceName: s.name, key: k.api_key }),
    onError: () => toast("Failed to create API key", "danger"),
  });

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Services</h2>
          <p className="text-sm text-slate-400">
            Each service is a backend + rate-limit policy behind a gateway endpoint.
          </p>
        </div>
        {!formOpen && (
          <Button variant="primary" onClick={() => setFormOpen(true)}>
            <PlusIcon /> New service
          </Button>
        )}
      </div>

      {formOpen && (
        <Card className="animate-fade-in">
          <CardHeader>
            <span className="text-sm font-medium text-slate-700">New service</span>
            <button
              className="text-slate-400 hover:text-slate-600"
              onClick={() => {
                setFormOpen(false);
                setError(null);
              }}
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </CardHeader>
          <CardBody>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                create.mutate();
              }}
              className="grid gap-3 sm:grid-cols-2"
            >
              <LabeledField label="Service name" className="sm:col-span-1">
                <input
                  className="input"
                  placeholder="Payments API"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </LabeledField>
              <LabeledField label="Backend URL" className="sm:col-span-1">
                <input
                  className="input"
                  placeholder="https://your-backend.example.com"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                />
              </LabeledField>
              <LabeledField label="Algorithm" className="sm:col-span-1">
                <select
                  className="select"
                  value={algorithm}
                  onChange={(e) => setAlgorithm(e.target.value as Algorithm)}
                >
                  {ALGORITHMS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </select>
              </LabeledField>
              <LabeledField label="Limit / window" className="sm:col-span-1">
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    className="input"
                    value={limit}
                    min={1}
                    onChange={(e) => setLimit(Number(e.target.value))}
                  />
                  <span className="shrink-0 text-sm text-slate-400">req /</span>
                  <input
                    type="number"
                    className="input"
                    value={windowSeconds}
                    min={1}
                    onChange={(e) => setWindowSeconds(Number(e.target.value))}
                  />
                  <span className="shrink-0 text-sm text-slate-400">s</span>
                </div>
              </LabeledField>

              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">
                  {error}
                </p>
              )}

              <div className="flex justify-end gap-2 sm:col-span-2">
                <Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" loading={create.isPending}>
                  Create service
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      {newKey && (
        <Card className="animate-fade-in border-amber-300 bg-amber-50">
          <CardBody>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-amber-900">
                  New key for "{newKey.serviceName}" — copy it now, it won't be shown again
                </p>
                <code className="mt-2 block break-all rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs text-slate-700">
                  {newKey.key}
                </code>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <CopyButton value={newKey.key} label="Copy key" />
              <button
                className="text-xs text-amber-700 underline hover:text-amber-900"
                onClick={() => setNewKey(null)}
              >
                Dismiss
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="grid gap-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : services.length === 0 ? (
        <EmptyState
          icon={<ServerIcon />}
          title="No services yet"
          description="Register your first backend to get a gateway endpoint and API key."
          action={
            <Button variant="primary" onClick={() => setFormOpen(true)}>
              <PlusIcon /> New service
            </Button>
          }
        />
      ) : (
        <ul className="space-y-3">
          {services.map((s) => (
            <li key={s.id}>
              <Card>
                <CardBody>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{s.name}</span>
                      <Badge tone={s.is_active ? "success" : "neutral"}>
                        {s.is_active ? "active" : "inactive"}
                      </Badge>
                      <Badge tone="brand">{algoLabel(s.rule.algorithm)}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                        <ChartIcon />
                        {openId === s.id ? "Hide dashboard" : "Dashboard"}
                      </Button>
                      <Button size="sm" onClick={() => mintKey.mutate(s)} loading={mintKey.isPending}>
                        <KeyIcon /> New key
                      </Button>
                      {confirmDeleteId === s.id ? (
                        <div className="flex items-center gap-1.5 rounded-lg bg-red-50 px-2 py-1">
                          <span className="text-xs text-red-700">Delete?</span>
                          <button
                            className="text-xs font-semibold text-red-700 underline"
                            onClick={() => remove.mutate(s.id)}
                          >
                            Yes
                          </button>
                          <button
                            className="text-xs text-slate-500 underline"
                            onClick={() => setConfirmDeleteId(null)}
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <Button size="sm" variant="danger" onClick={() => setConfirmDeleteId(s.id)}>
                          <TrashIcon />
                        </Button>
                      )}
                    </div>
                  </div>

                  <p className="mt-2 truncate text-sm text-slate-500">→ {s.upstream_url}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {s.rule.limit} req / {s.rule.window_seconds}s per client IP
                    {s.rule.burst ? ` · burst ${s.rule.burst}` : ""}
                  </p>

                  <div className="mt-2 flex items-center gap-1">
                    <span className="rounded bg-slate-50 px-1.5 py-0.5 font-mono text-[11px] text-slate-500">
                      /gw/{s.public_id}
                    </span>
                    <CopyButton value={s.public_id} label="" />
                  </div>

                  {openId === s.id && (
                    <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2">
                      <UsageCharts serviceId={s.id} />
                      <LiveFeed serviceId={s.id} />
                    </div>
                  )}
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LabeledField({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}
function CloseIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
function ChartIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M8 17V9m4 8V5m4 12v-6" />
    </svg>
  );
}
function KeyIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
      />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
      />
    </svg>
  );
}
function ServerIcon() {
  return (
    <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21.75 17.25v-.228a4.5 4.5 0 00-.12-1.03l-2.268-9.64a3.375 3.375 0 00-3.285-2.602H7.923a3.375 3.375 0 00-3.285 2.602l-2.268 9.64a4.5 4.5 0 00-.12 1.03v.228m19.5 0a3 3 0 01-3 3H5.25a3 3 0 01-3-3m19.5 0a3 3 0 00-3-3H5.25a3 3 0 00-3 3m16.5 0h.008v.008h-.008v-.008zm-3 0h.008v.008h-.008v-.008z"
      />
    </svg>
  );
}
