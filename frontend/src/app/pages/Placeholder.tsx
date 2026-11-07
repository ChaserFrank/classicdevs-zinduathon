/**
 * Route skeletons for Phase 1 only (frontend docs/ROUTES.md). Each is replaced by its real screen
 * in the phase noted; none of them calls the API.
 */
import { Link } from "react-router-dom";

import { GlassPanel } from "@/components/glass/Glass";

export function AuthPlaceholder() {
  return (
    <GlassPanel glow scrim className="p-8 text-center">
      <h2 className="text-2xl">Sign-in arrives in phase 2</h2>
      <p className="mt-2 text-sm text-mist">This route exists so the layout can be reviewed.</p>
      <Link to="/" className="mt-6 inline-block text-sm text-flare-hot hover:underline">
        Back home
      </Link>
    </GlassPanel>
  );
}

export function AppPlaceholder() {
  return (
    <GlassPanel className="p-8">
      <h2 className="text-2xl">The job seeker dashboard arrives in phase 3</h2>
      <p className="mt-2 text-sm text-mist">The shell, sidebar and backdrop are final.</p>
    </GlassPanel>
  );
}
