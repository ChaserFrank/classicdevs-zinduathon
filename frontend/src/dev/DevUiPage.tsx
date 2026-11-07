/**
 * /dev/ui (development builds only): every glass component and state on one page for design
 * review, plus the browser → API health check that proves CORS is configured.
 */
import { CheckCircle2, XCircle } from "lucide-react";

import { GlassCard, GlassPanel, GlassPill } from "@/components/glass/Glass";
import { SignalPlanet } from "@/components/space/SignalPlanet";
import { useProgressGlow } from "@/components/space/progress-glow";
import { SpaceBackdrop } from "@/components/space/SpaceBackdrop";
import { ClaimBadge, StatusChip, TierBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { EmptyState, ErrorState, SkeletonBlock, StatTile } from "@/components/ui/States";
import { Wordmark } from "@/components/brand/Logo";
import { API_BASE_URL } from "@/lib/api/client";
import { ApiError, userMessage } from "@/lib/api/errors";
import { useHealth } from "@/lib/api/health";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-xl">{title}</h2>
      {children}
    </section>
  );
}

function HealthCheck() {
  const { data, error, isPending, refetch, isFetching } = useHealth();
  const ok = data?.status === "ok";
  return (
    <GlassPanel glow className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg">Browser → API</h3>
          <p className="font-mono text-sm text-mist">GET {API_BASE_URL}/health</p>
        </div>
        <Button variant="glass" size="sm" loading={isFetching} onClick={() => refetch()}>
          Check again
        </Button>
      </div>
      <div className="mt-4 flex items-start gap-3" data-testid="health-result">
        {isPending ? (
          <SkeletonBlock lines={2} label="Checking the API" />
        ) : ok ? (
          <>
            <CheckCircle2 aria-hidden className="mt-0.5 h-5 w-5 text-ok" />
            <p>
              Reached the API: database <b>{data.checks.database}</b>, redis <b>{data.checks.redis}</b>,
              version {data.version}. CORS is configured for this origin.
            </p>
          </>
        ) : (
          <>
            <XCircle aria-hidden className="mt-0.5 h-5 w-5 text-bad" />
            <div>
              <p>
                {error instanceof ApiError && error.status === 0
                  ? "The browser couldn't reach the API."
                  : userMessage(error)}
              </p>
              <p className="mt-1 text-sm text-mist">
                If the API is running, add <code className="text-ink">{window.location.origin}</code> to{" "}
                <code className="text-ink">CORS_ALLOWED_ORIGINS</code> in <code>backend/.env</code> and
                restart it.
              </p>
            </div>
          </>
        )}
      </div>
    </GlassPanel>
  );
}

function GlowSteps() {
  const { step, setStep } = useProgressGlow();
  return (
    <div className="flex flex-wrap items-center gap-2">
      {[0, 1, 2, 3, 4, 5].map((s) => (
        <Button key={s} size="sm" variant={s === step ? "primary" : "glass"} onClick={() => setStep(s)}>
          {s === 0 ? "Idle" : s === 5 ? "Card" : `Step ${s}`}
        </Button>
      ))}
    </div>
  );
}

export function DevUiPage() {
  return (
    <div className="relative min-h-screen">
      <SpaceBackdrop />
      <div className="mx-auto max-w-6xl space-y-12 px-4 py-10">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <Wordmark className="text-xl" />
          <GlassPill className="text-mist">/dev/ui · development only</GlassPill>
        </header>

        <HealthCheck />

        <Section title="Glass tiers">
          <div className="grid gap-4 md:grid-cols-3">
            <GlassPanel className="p-6">
              <h3 className="text-lg">GlassPanel</h3>
              <p className="mt-1 text-sm text-mist">24px radius, blur 24px, floats over the backdrop.</p>
            </GlassPanel>
            <GlassPanel glow className="p-6">
              <h3 className="text-lg">GlassPanel glow</h3>
              <p className="mt-1 text-sm text-mist">One per screen: the thing that matters most.</p>
            </GlassPanel>
            <GlassPanel className="space-y-3 p-6">
              <GlassCard className="p-4">
                <h3 className="text-base">GlassCard</h3>
                <p className="text-sm text-mist">16px radius, lighter blur.</p>
              </GlassCard>
              <div className="flex flex-wrap gap-2">
                <GlassPill>GlassPill</GlassPill>
                <GlassPill className="text-mist">Filter</GlassPill>
              </div>
            </GlassPanel>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Run analysis</Button>
            <Button variant="hero">Get your skill card</Button>
            <Button variant="glass">I'm hiring</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete account</Button>
            <Button loading>Sending</Button>
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
            <Button disabled>Disabled</Button>
          </div>
        </Section>

        <Section title="Fields">
          <GlassPanel className="grid gap-6 p-6 md:grid-cols-2">
            <Field label="Email" hint="We'll send a verification link.">
              {({ id, describedBy }) => (
                <Input id={id} aria-describedby={describedBy} type="email" placeholder="you@example.com" />
              )}
            </Field>
            <Field label="Password" error="Use at least 8 characters.">
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="password"
                  defaultValue="short"
                />
              )}
            </Field>
          </GlassPanel>
        </Section>

        <Section title="Badges and status">
          <GlassPanel className="flex flex-wrap items-center gap-3 p-6">
            <TierBadge tier="Strong" />
            <TierBadge tier="Moderate" />
            <TierBadge tier="Emerging" />
            <TierBadge tier="Unverified" />
            <span className="mx-2 h-5 w-px bg-white/10" />
            <ClaimBadge status="Verified" />
            <ClaimBadge status="Partly" />
            <ClaimBadge status="Unverified" />
            <span className="mx-2 h-5 w-px bg-white/10" />
            <StatusChip tone="ok">Delivered</StatusChip>
            <StatusChip tone="warn">Pending</StatusChip>
            <StatusChip tone="bad">Failed</StatusChip>
            <StatusChip>Dry run</StatusChip>
          </GlassPanel>
        </Section>

        <Section title="States">
          <div className="grid gap-4 md:grid-cols-3">
            <GlassPanel className="p-6">
              <SkeletonBlock lines={4} />
            </GlassPanel>
            <GlassPanel>
              <EmptyState
                title="No feedback yet"
                description="When recruiters send feedback, it lands here."
                action={<Button size="sm">Share your card</Button>}
              />
            </GlassPanel>
            <GlassPanel>
              <ErrorState
                description="We couldn't load your analyses."
                onRetry={() => undefined}
                requestId="4b8e22652d5d4b01"
              />
            </GlassPanel>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
            <StatTile label="Signal Score" value="74" hint="+6 since last analysis" />
            <StatTile label="Profile views" value="3" hint="this week" />
            <StatTile label="Pending recruiters" value="1" />
            <StatTile label="SMS delivered" value="98%" />
          </div>
        </Section>

        <Section title="Backdrop glow (analysis progress)">
          <GlowSteps />
        </Section>

        <Section title="Signal Planet">
          <GlassPanel className="relative h-[460px] overflow-hidden p-0">
            <SignalPlanet />
          </GlassPanel>
        </Section>
      </div>
    </div>
  );
}
