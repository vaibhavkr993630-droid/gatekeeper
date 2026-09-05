import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, authApi, setToken } from "../api";
import Button from "../components/ui/Button";

type Mode = "login" | "register";

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setPassword(""); // never carry a typed password across the login/register switch
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res =
        mode === "login"
          ? await authApi.login({ email, password })
          : await authApi.register({ tenant_name: tenantName, email, password });
      setToken(res.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-base font-bold text-white shadow-sm">
            G
          </div>
          <span className="text-lg font-semibold tracking-tight text-slate-900">GateKeeper</span>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white shadow-card">
          {/* Tabbed switcher — the whole point is that "I don't have an account yet"
              is a first-class, equally-visible choice, not a footnote link. */}
          <div className="grid grid-cols-2 gap-1 p-1.5">
            <TabButton active={mode === "login"} onClick={() => switchMode("login")}>
              Sign in
            </TabButton>
            <TabButton active={mode === "register"} onClick={() => switchMode("register")}>
              Create account
            </TabButton>
          </div>

          <form onSubmit={submit} className="space-y-4 border-t border-slate-100 p-6 pt-5">
            <div>
              <h1 className="text-base font-semibold text-slate-900">
                {mode === "login" ? "Welcome back" : "Create your account"}
              </h1>
              <p className="mt-0.5 text-sm text-slate-400">
                {mode === "login"
                  ? "Sign in to manage your services and rate limits."
                  : "Register a tenant and get your gateway endpoint + API key."}
              </p>
            </div>

            {mode === "register" && (
              <Field label="Company name">
                <input
                  className="input"
                  placeholder="Acme Inc."
                  value={tenantName}
                  onChange={(e) => setTenantName(e.target.value)}
                  required
                  autoFocus
                />
              </Field>
            )}
            <Field label="Email">
              <input
                className="input"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus={mode === "login"}
              />
            </Field>
            <Field label="Password">
              <input
                className="input"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </Field>

            {error && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                <p>{error}</p>
                {mode === "login" && (
                  <p className="mt-1 text-xs text-red-600">
                    New here?{" "}
                    <button
                      type="button"
                      className="font-medium underline underline-offset-2"
                      onClick={() => switchMode("register")}
                    >
                      Create an account
                    </button>{" "}
                    instead — it takes a few seconds.
                  </p>
                )}
              </div>
            )}

            <Button type="submit" variant="primary" loading={loading} className="w-full justify-center">
              {mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-400">
          Platform operator?{" "}
          <a href="/admin/login" className="underline hover:text-slate-600">
            Admin sign in
          </a>
        </p>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg py-2 text-sm font-medium transition-colors ${
        active ? "bg-brand-50 text-brand-700" : "text-slate-400 hover:bg-slate-50 hover:text-slate-600"
      }`}
    >
      {children}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}
