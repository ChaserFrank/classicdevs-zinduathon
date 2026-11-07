import { useMemo, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { ProgressGlowContext, useProgressGlow } from "./progress-glow";

export function ProgressGlowProvider({ children }: { children: ReactNode }) {
  const [step, setStep] = useState(0);
  const value = useMemo(() => ({ step, setStep }), [step]);
  return <ProgressGlowContext.Provider value={value}>{children}</ProgressGlowContext.Provider>;
}

const STRENGTH = [0.55, 0.65, 0.75, 0.88, 1, 0.7];

/**
 * In-app background: near-black space, a planet just out of frame at the top right (one huge
 * orange arc), faint star dust and 4% grain. No WebGL: it must cost nothing on app screens.
 */
export function SpaceBackdrop({ className }: { className?: string }) {
  const { step } = useProgressGlow();
  const strength = STRENGTH[Math.min(step, STRENGTH.length - 1)] ?? 0.55;
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-void", className)}
    >
      <div
        className="absolute -right-[62vmax] -top-[74vmax] h-[110vmax] w-[110vmax] rounded-full transition-[opacity,transform] duration-700"
        style={{
          opacity: strength * 0.75,
          transform: `scale(${0.97 + strength * 0.05})`,
          filter: "blur(1.5px)",
          // The body is near-void so it reads as a dark planet, not a disc; only the rim glows.
          background:
            "radial-gradient(closest-side, rgb(var(--void-2)) 90%, rgb(var(--ember) / 0.35) 95%, rgb(var(--flare) / 0.55) 97.6%, rgb(var(--flare-hot) / 0.35) 98.6%, transparent 100%)",
          boxShadow: "0 0 220px 30px rgb(var(--flare) / 0.10)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.55]"
        style={{
          backgroundImage:
            "radial-gradient(1px 1px at 12% 22%, #fff8 50%, transparent), radial-gradient(1px 1px at 72% 64%, #fff6 50%, transparent), radial-gradient(1px 1px at 38% 82%, #fff5 50%, transparent), radial-gradient(1px 1px at 88% 12%, #fff7 50%, transparent), radial-gradient(1px 1px at 54% 38%, #fff4 50%, transparent), radial-gradient(1px 1px at 22% 58%, #fff5 50%, transparent)",
          backgroundSize: "640px 640px",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.04] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
    </div>
  );
}
