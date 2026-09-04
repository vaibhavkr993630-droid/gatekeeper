const TOKEN_KEY = "gk_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export interface Token {
  access_token: string;
}
export interface Me {
  id: number;
  email: string;
  tenant: { id: number; name: string; plan: string };
}

export const authApi = {
  register: (body: { tenant_name: string; email: string; password: string }) =>
    request<Token>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<Token>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<Me>("/auth/me"),
};

export type Algorithm = "token_bucket" | "sliding_window_counter";

export interface Rule {
  algorithm: Algorithm;
  limit: number;
  window_seconds: number;
  burst: number | null;
}

export interface Service {
  id: number;
  public_id: string;
  name: string;
  upstream_url: string;
  is_active: boolean;
  rule: Rule;
  created_at: string;
}

export interface ApiKey {
  id: number;
  name: string | null;
  prefix: string;
  last_four: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface StatPoint {
  minute: string;
  requests: number;
  blocked: number;
}
export interface ServiceStats {
  service_id: number;
  window_minutes: number;
  rule: Rule;
  totals: { requests: number; blocked: number; block_rate: number };
  series: StatPoint[];
}

export interface FeedEvent {
  type: "request";
  service_id: number;
  service_name: string;
  allowed: boolean;
  status_code: number;
  method: string;
  path: string;
  client_ip: string;
  rule_algorithm: string | null;
  latency_ms: number | null;
  at: string;
}

export const servicesApi = {
  list: () => request<Service[]>("/services"),
  stats: (id: number, minutes = 60) =>
    request<ServiceStats>(`/services/${id}/stats?minutes=${minutes}`),
  create: (body: { name: string; upstream_url: string; rule: Rule }) =>
    request<Service>("/services", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: number) =>
    fetch(`/api/services/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${getToken()}` },
    }).then((r) => {
      if (!r.ok) throw new Error("Delete failed");
    }),
  listKeys: (id: number) => request<ApiKey[]>(`/services/${id}/keys`),
  createKey: (id: number, name: string) =>
    request<ApiKey & { api_key: string }>(`/services/${id}/keys`, {
      method: "POST",
      body: JSON.stringify({ name: name || null }),
    }),
};
