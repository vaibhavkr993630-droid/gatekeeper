import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminApi, ApiError, setAdminToken } from "../api";
import Button from "../components/ui/Button";

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await adminApi.login({ email, password });
      setAdminToken(res.access_token);
      navigate("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-base font-bold text-slate-900">
            G
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold tracking-tight text-white">GateKeeper</div>
            <div className="text-[11px] uppercase tracking-widest text-slate-500">Platform Ops</div>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-7 shadow-xl"
        >
          <div>
            <h1 className="text-base font-semibold text-white">Admin sign in</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              System-wide operational view. Not for tenant accounts.
            </p>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-400">Email</span>
            <input
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-900"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-400">Password</span>
            <input
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-900"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && (
            <p className="rounded-lg bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>
          )}

          <Button type="submit" variant="primary" loading={loading} className="w-full justify-center">
            Sign in
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-600">
          Looking for your tenant dashboard?{" "}
          <a href="/login" className="underline hover:text-slate-400">
            Sign in here
          </a>
        </p>
      </div>
    </div>
  );
}
