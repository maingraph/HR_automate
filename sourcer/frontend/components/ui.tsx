"use client";

import { type ReactNode } from "react";

// ── Badge ─────────────────────────────────────────────────────────────────

const badgeVariants = {
  default:    "bg-[var(--panel2)] text-[var(--fg2)] border border-[var(--border)]",
  active:     "bg-green-900/40 text-green-400 border border-green-800/50",
  sent:       "bg-blue-900/40 text-blue-400 border border-blue-800/50",
  replied:    "bg-purple-900/40 text-purple-400 border border-purple-800/50",
  qualified:  "bg-emerald-900/40 text-emerald-400 border border-emerald-800/50",
  rejected:   "bg-red-900/40 text-red-400 border border-red-800/50",
  pending:    "bg-amber-900/40 text-amber-400 border border-amber-800/50",
  draft:      "bg-[var(--panel2)] text-[var(--muted)] border border-[var(--border)]",
  copilot:    "bg-blue-900/40 text-blue-300 border border-blue-800/50",
  autopilot:  "bg-purple-900/40 text-purple-300 border border-purple-800/50",
  interested: "bg-green-900/40 text-green-400 border border-green-800/50",
  questions:  "bg-amber-900/40 text-amber-400 border border-amber-800/50",
  declined:   "bg-red-900/40 text-red-400 border border-red-800/50",
  other:      "bg-[var(--panel2)] text-[var(--muted)] border border-[var(--border)]",
} as const;

export function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: ReactNode;
  variant?: keyof typeof badgeVariants;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium ${badgeVariants[variant]} ${className}`}>
      {children}
    </span>
  );
}

// ── Button ────────────────────────────────────────────────────────────────

type BtnVariant = "primary" | "secondary" | "ghost" | "danger" | "success";

const btnVariants: Record<BtnVariant, string> = {
  primary:   "bg-[var(--accent)] text-white hover:bg-[var(--accent2)] shadow-sm shadow-[var(--accent-glow)]",
  secondary: "bg-[var(--panel2)] text-[var(--fg)] border border-[var(--border)] hover:border-[var(--border2)] hover:bg-[var(--panel)]",
  ghost:     "text-[var(--fg2)] hover:text-[var(--fg)] hover:bg-[var(--panel2)]",
  danger:    "bg-red-900/40 text-red-400 border border-red-800/50 hover:bg-red-900/60",
  success:   "bg-green-900/40 text-green-400 border border-green-800/50 hover:bg-green-900/60",
};

export function Btn({
  children,
  variant = "secondary",
  className = "",
  size = "md",
  disabled,
  loading,
  onClick,
  type = "button",
}: {
  children: ReactNode;
  variant?: BtnVariant;
  className?: string;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
}) {
  const sizes = { sm: "px-2.5 py-1 text-xs", md: "px-3.5 py-1.5 text-sm", lg: "px-5 py-2.5 text-sm" };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-1.5 rounded-lg font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed ${sizes[size]} ${btnVariants[variant]} ${className}`}
    >
      {loading ? <Spinner size="sm" /> : null}
      {children}
    </button>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const s = { sm: "w-3 h-3", md: "w-4 h-4", lg: "w-5 h-5" };
  return (
    <svg className={`animate-spin ${s[size]} text-current`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────

export function Card({
  children,
  className = "",
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-[var(--panel)] border border-[var(--border)] rounded-xl ${onClick ? "cursor-pointer hover:border-[var(--border2)] hover:bg-[var(--panel2)]" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

// ── Section header ────────────────────────────────────────────────────────

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--fg)]">{title}</h1>
        {subtitle && <p className="text-sm text-[var(--muted)] mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}

// ── Form field ────────────────────────────────────────────────────────────

export const inputCls =
  "w-full rounded-lg bg-[var(--bg2)] border border-[var(--border)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]/20";

export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`grid gap-1.5 ${className || ""}`}>
      <span className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
        {label}
        {required && <span className="text-red-400 ml-1">*</span>}
      </span>
      {children}
      {error && <span className="text-xs text-red-400">{error}</span>}
      {hint && <span className="text-xs text-[var(--muted)] opacity-70">{hint}</span>}
    </label>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────

export function Empty({ icon, title, subtitle }: { icon: string; title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-3">{icon}</div>
      <p className="font-medium text-[var(--fg2)]">{title}</p>
      {subtitle && <p className="text-sm text-[var(--muted)] mt-1">{subtitle}</p>}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────

export function StatCard({ label, value, sub, color = "default" }: {
  label: string;
  value: string | number;
  sub?: string;
  color?: "default" | "green" | "blue" | "purple" | "amber";
}) {
  const colors = {
    default: "text-[var(--fg)]",
    green:   "text-green-400",
    blue:    "text-blue-400",
    purple:  "text-purple-400",
    amber:   "text-amber-400",
  };
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wider text-[var(--muted)] mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colors[color]}`}>{value}</p>
      {sub && <p className="text-xs text-[var(--muted)] mt-0.5">{sub}</p>}
    </Card>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors ${checked ? "bg-[var(--accent)]" : "bg-[var(--border2)]"}`}
      >
        <div
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0"}`}
        />
      </div>
      {label && <span className="text-sm text-[var(--fg2)]">{label}</span>}
    </label>
  );
}
