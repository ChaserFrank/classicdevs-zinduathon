import { cn } from "@/lib/utils";

/** The brand glyph: an orange rounded square holding a signal pulse (planet rim + evidence dot). */
export function LogoGlyph({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid h-7 w-7 place-items-center rounded-lg bg-flare shadow-[0_0_18px_-4px_rgb(var(--flare))]",
        className,
      )}
    >
      <svg
        viewBox="0 0 24 24"
        className="h-4 w-4"
        fill="none"
        stroke="black"
        strokeWidth="2.4"
        strokeLinecap="round"
      >
        <path d="M4 15a8 8 0 0 1 16 0" />
        <circle cx="12" cy="15" r="2" fill="black" stroke="none" />
      </svg>
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-bold tracking-tightest", className)}>
      <LogoGlyph />
      <span>SkillProof</span>
    </span>
  );
}
