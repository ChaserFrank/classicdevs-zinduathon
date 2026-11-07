import { Github } from "lucide-react";
import { useState, type ReactNode } from "react";

import { GlassPanel } from "@/components/glass/Glass";
import { Button } from "@/components/ui/Button";
import { userMessage } from "@/lib/api/errors";

import { startGithub } from "./github";

export function AuthCard({ title, subtitle, children, footer }: { title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <GlassPanel glow scrim as="section" aria-labelledby="auth-title" className="p-7 sm:p-8">
      <h1 id="auth-title" className="text-2xl">
        {title}
      </h1>
      {subtitle && <p className="mt-1.5 text-sm text-mist">{subtitle}</p>}
      <div className="mt-6">{children}</div>
      {footer && <div className="mt-6 border-t border-line pt-5 text-center text-sm text-mist">{footer}</div>}
    </GlassPanel>
  );
}

export function Divider({ label = "or" }: { label?: string }) {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-mist">
      <span className="h-px flex-1 bg-white/10" />
      {label}
      <span className="h-px flex-1 bg-white/10" />
    </div>
  );
}

export function GithubButton({ label = "Continue with GitHub", options, onError }: { label?: string; options?: Parameters<typeof startGithub>[0]; onError?: (m: string) => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      type="button"
      variant="glass"
      className="w-full"
      loading={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await startGithub(options);
        } catch (e) {
          setBusy(false);
          onError?.(userMessage(e));
        }
      }}
    >
      <Github aria-hidden className="h-4 w-4" />
      {label}
    </Button>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mb-4 rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-sm text-bad">
      {message}
    </p>
  );
}
