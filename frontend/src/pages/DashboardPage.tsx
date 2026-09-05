import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi, clearToken } from "../api";
import AppShell from "../components/AppShell";
import ServicesPanel from "../components/ServicesPanel";
import Badge from "../components/ui/Badge";
import { SkeletonCard } from "../components/ui/Skeleton";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({ queryKey: ["me"], queryFn: authApi.me });

  function logout() {
    clearToken();
    navigate("/login");
  }

  if (isError) {
    clearToken();
    navigate("/login");
    return null;
  }

  return (
    <AppShell
      subtitle={data?.tenant.name}
      identity={data ? `${data.email}` : undefined}
      onLogout={logout}
    >
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <>
          <div className="mb-6 flex items-center gap-2">
            <h1 className="text-lg font-semibold text-slate-900">{data?.tenant.name}</h1>
            <Badge tone="brand">{data?.tenant.plan} plan</Badge>
          </div>
          <ServicesPanel />
        </>
      )}
    </AppShell>
  );
}
