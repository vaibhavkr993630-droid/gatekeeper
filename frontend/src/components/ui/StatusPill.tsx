import type { ReactNode } from "react";

type Tone = "success" | "danger" | "warning" | "neutral";

const dot: Record<Tone, string> = {
  success: "bg-emerald-500",
  danger: "bg-red-500",
  warning: "bg-amber-500",
  neutral: "bg-slate-400",
};

const text: Record<Tone, string> = {
  success: "text-emerald-700",
  danger: "text-red-700",
  warning: "text-amber-700",
  neutral: "text-slate-500",
};

export default function StatusPill({
  tone,
  children,
  pulse = false,
}: {
  tone: Tone;
  children: ReactNode;
  pulse?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${text[tone]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot[tone]} ${pulse ? "animate-pulse-dot" : ""}`} />
      {children}
    </span>
  );
}
