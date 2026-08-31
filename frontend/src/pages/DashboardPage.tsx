import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi, clearToken } from "../api";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({ queryKey: ["me"], queryFn: authApi.me });

  function logout() {
    clearToken();
    navigate("/login");
  }

  if (isLoading) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (isError) {
    clearToken();
    navigate("/login");
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <span className="font-semibold">GateKeeper</span>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-500">
            {data?.email} · {data?.tenant.name} ({data?.tenant.plan})
          </span>
          <button onClick={logout} className="text-slate-500 underline">
            Log out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl p-6">
        <h1 className="text-lg font-semibold">Services</h1>
        <div className="mt-4 rounded-lg border border-dashed bg-white p-10 text-center text-sm text-slate-400">
          No services yet. Service registration arrives in Phase 2.
        </div>
      </main>
    </div>
  );
}
