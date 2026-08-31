import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, setToken } from "../api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res =
        mode === "login"
          ? await authApi.login({ email, password })
          : await authApi.register({ tenant_name: tenantName, email, password });
      setToken(res.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <form onSubmit={submit} className="w-80 space-y-3 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">GateKeeper</h1>
        <p className="text-sm text-slate-500">
          {mode === "login" ? "Sign in to your dashboard" : "Create a tenant account"}
        </p>
        {mode === "register" && (
          <input
            className="w-full rounded border p-2 text-sm"
            placeholder="Company name"
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            required
          />
        )}
        <input
          className="w-full rounded border p-2 text-sm"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="w-full rounded border p-2 text-sm"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-slate-900 p-2 text-sm text-white" type="submit">
          {mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          className="w-full text-xs text-slate-500 underline"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
