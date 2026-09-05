import type { ReactNode } from "react";
import Badge from "./ui/Badge";

export default function AppShell({
  subtitle,
  admin = false,
  identity,
  onLogout,
  children,
}: {
  subtitle?: string;
  admin?: boolean;
  identity?: string;
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-sm font-bold text-white">
              G
            </div>
            <span className="font-semibold tracking-tight">GateKeeper</span>
            {admin && <Badge tone="brand">Admin</Badge>}
            {subtitle && <span className="hidden text-sm text-slate-400 sm:inline">· {subtitle}</span>}
          </div>
          <div className="flex items-center gap-4 text-sm">
            {identity && <span className="hidden text-slate-500 sm:inline">{identity}</span>}
            <button onClick={onLogout} className="text-slate-500 underline decoration-slate-300 underline-offset-2 hover:text-slate-800">
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
