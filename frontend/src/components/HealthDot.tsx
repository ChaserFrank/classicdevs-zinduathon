import { useHealth } from "@/lib/api/health";
import { cn } from "@/lib/utils";

/** Dev-only footer dot: is the browser able to reach the API (incl. CORS)? */
export function HealthDot() {
  const { data, isError, isPending } = useHealth();
  const ok = data?.status === "ok";
  return (
    <span className="inline-flex items-center gap-1.5" title="API health (dev only)">
      <span
        aria-hidden
        className={cn(
          "h-2 w-2 rounded-full",
          isPending ? "bg-mist" : ok ? "bg-ok" : "bg-bad",
          isError && "bg-bad",
        )}
      />
      API {isPending ? "…" : ok ? "ok" : isError ? "unreachable" : data?.status}
    </span>
  );
}
