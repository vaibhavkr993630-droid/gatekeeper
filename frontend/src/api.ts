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
