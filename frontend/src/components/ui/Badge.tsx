import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type Tier = "Strong" | "Moderate" | "Emerging" | "Unverified";
export type ClaimStatus = "Verified" | "Partly" | "Unverified";

const tierStyle: Record<Tier, string> = {
  Strong: "bg-flare text-black border-flare",
  Moderate: "border-flare text-flare-hot",
  Emerging: "border-mist/60 text-mist",
  Unverified: "border-dashed border-bad/80 text-bad",
};

/** Skill tier, never colour alone: the label text is always shown. */
export function TierBadge({ tier, className }: { tier: Tier; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-semibold",
        tierStyle[tier],
        className,
      )}
    >
      {tier}
    </span>
  );
}

const claimStyle: Record<ClaimStatus, string> = {
  Verified: "border-ok/60 text-ok",
  Partly: "border-warn/60 text-warn",
  Unverified: "border-dashed border-bad/70 text-bad",
};

export function ClaimBadge({ status }: { status: ClaimStatus }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-semibold",
        claimStyle[status],
      )}
    >
      {status}
    </span>
  );
}

type Tone = "neutral" | "ok" | "warn" | "bad" | "flare";
const tones: Record<Tone, string> = {
  neutral: "text-mist",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  flare: "text-flare-hot",
};

/** Small status label with a dot (delivered, pending, failed…). */
export function StatusChip({
  tone = "neutral",
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "glass-pill inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...rest}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}
