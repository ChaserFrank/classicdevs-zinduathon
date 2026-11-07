import { Wordmark } from "@/components/brand/Logo";

/** Glass splash while the session is restored (refresh + /me) before protected routes render. */
export function Splash() {
  return (
    <div
      role="status"
      aria-label="Loading SkillProof"
      className="grid min-h-screen place-items-center bg-void"
    >
      <div className="glass-panel flex items-center gap-3 rounded-full px-5 py-3">
        <Wordmark />
        <span
          aria-hidden
          className="h-2 w-2 animate-pulse rounded-full bg-flare shadow-[0_0_10px_rgb(var(--flare))]"
        />
      </div>
    </div>
  );
}
