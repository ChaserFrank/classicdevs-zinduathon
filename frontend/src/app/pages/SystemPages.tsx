import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

import { GlassPanel } from "@/components/glass/Glass";
import { StaticPlanet } from "@/components/space/SignalPlanet";
import { ApiError } from "@/lib/api/errors";

function Frame({ title, body, children }: { title: string; body: string; children?: React.ReactNode }) {
  return (
    <div className="relative isolate grid min-h-screen place-items-center overflow-hidden bg-void px-4">
      <StaticPlanet className="-z-10 opacity-60" />
      <GlassPanel glow scrim className="w-full max-w-md p-8 text-center">
        <h1 className="text-3xl">{title}</h1>
        <p className="mt-3 text-mist">{body}</p>
        <div className="mt-6 flex justify-center gap-3">{children}</div>
      </GlassPanel>
    </div>
  );
}

export function NotFound() {
  return (
    <Frame
      title="This page is noise"
      body="There's no signal at this address. The link may be old or mistyped."
    >
      <Link
        to="/"
        className="inline-flex h-10 items-center rounded-full bg-ink px-5 text-sm font-semibold text-black"
      >
        Back to SkillProof
      </Link>
    </Frame>
  );
}

export function RouteError() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  return (
    <Frame
      title="Something broke on this screen"
      body="Reload to try again. If it keeps happening, send us the request ID below."
    >
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="inline-flex h-10 items-center rounded-full bg-ink px-5 text-sm font-semibold text-black"
      >
        Reload
      </button>
      {requestId && <p className="font-mono text-xs text-mist">Request ID {requestId}</p>}
    </Frame>
  );
}
