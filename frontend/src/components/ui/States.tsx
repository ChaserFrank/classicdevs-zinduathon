import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";

import { cn } from "@/lib/utils";

import { Button } from "./Button";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-lg bg-white/[0.06]", className)} />;
}

/** Loading placeholder that keeps the layout's shape and tells screen readers what's happening. */
export function SkeletonBlock({ lines = 3, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

type StateProps = {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, icon, className }: StateProps) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl border border-line bg-white/5 text-mist">
        {icon ?? <Inbox aria-hidden className="h-5 w-5" />}
      </div>
      <h3 className="text-lg">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-mist">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "That didn't load",
  description,
  onRetry,
  requestId,
  className,
}: Omit<StateProps, "action" | "title"> & { title?: string; onRetry?: () => void; requestId?: string }) {
  return (
    <div role="alert" className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl border border-bad/30 bg-bad/10 text-bad">
        <AlertTriangle aria-hidden className="h-5 w-5" />
      </div>
      <h3 className="text-lg">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-mist">{description}</p>}
      {onRetry && (
        <Button variant="glass" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
      {requestId && <p className="mt-3 font-mono text-xs text-mist/80">Request ID {requestId}</p>}
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass-card rounded-card p-4", className)}>
      <p className="text-sm text-mist">{label}</p>
      <p className="tabular mt-1 text-2xl font-bold">{value}</p>
      {hint && <p className="mt-1 text-xs text-mist">{hint}</p>}
    </div>
  );
}
