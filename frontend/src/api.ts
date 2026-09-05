const TOKEN_KEY = "gk_token";
const ADMIN_TOKEN_KEY = "gk_admin_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_KEY);
export const setAdminToken = (t: string) => localStorage.setItem(ADMIN_TOKEN_KEY, t);
export const clearAdminToken = () => localStorage.removeItem(ADMIN_TOKEN_KEY);

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  opts: RequestInit = {},
  tokenGetter: () => string | null = getToken,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  const token = tokenGetter();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(detail.detail ?? `Request failed (${res.status})`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const adminRequest = <T>(path: string, opts: RequestInit = {}) =>
  request<T>(path, opts, getAdminToken);

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
  update: (id: number, body: Partial<{ name: string; upstream_url: string; is_active: boolean }>) =>
    request<Service>(`/services/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => request<void>(`/services/${id}`, { method: "DELETE" }),
  listKeys: (id: number) => request<ApiKey[]>(`/services/${id}/keys`),
  createKey: (id: number, name: string) =>
    request<ApiKey & { api_key: string }>(`/services/${id}/keys`, {
      method: "POST",
      body: JSON.stringify({ name: name || null }),
    }),
  revokeKey: (id: number, keyId: number) =>
    request<void>(`/services/${id}/keys/${keyId}`, { method: "DELETE" }),
};

// --- platform admin ----------------------------------------------------------

export interface AdminMe {
  id: number;
  email: string;
}
export interface TenantUsage {
  tenant_id: number;
  name: string;
  plan: string;
  requests_24h: number;
  daily_limit: number;
  pct_used: number;
}
export interface SystemOverview {
  tenants_total: number;
  services_total: number;
  requests_24h: number;
  blocked_24h: number;
  error_rate_24h: number;
  avg_latency_ms_24h: number | null;
  redis_ok: boolean;
  db_ok: boolean;
  requests_series_60m: StatPoint[];
  tenants_near_limit: TenantUsage[];
}

export const adminApi = {
  login: (body: { email: string; password: string }) =>
    request<Token>("/admin/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => adminRequest<AdminMe>("/admin/me"),
  overview: () => adminRequest<SystemOverview>("/admin/overview"),
};
