/** /dev/planet-capture (development only): renders the planet on a transparent page so
 * scripts/capture-static-planet.mjs can save public/images/planet-static.webp from the real scene. */
import { lazy, Suspense } from "react";

const Scene = lazy(() => import("@/components/space/SignalPlanetScene"));

export function PlanetCapturePage() {
  return (
    <div style={{ width: 1600, height: 900, background: "transparent" }} data-testid="planet-capture">
      <Suspense fallback={null}>
        <Scene intro={false} paused={false} capture />
      </Suspense>
    </div>
  );
}
