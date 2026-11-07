import { Link, Outlet } from "react-router-dom";

import { Wordmark } from "@/components/brand/Logo";
import { SignalPlanet } from "@/components/space/SignalPlanet";

/** Auth screens: the same black space with the planet glowing low behind a centred glass panel. */
export function AuthLayout() {
  return (
    <div className="relative isolate flex min-h-screen flex-col items-center overflow-hidden bg-void px-4 pb-16 pt-10">
      <SignalPlanet className="-z-10 opacity-70" />
      <Link to="/" aria-label="SkillProof home" className="mb-3">
        <Wordmark className="text-lg" />
      </Link>
      <p className="mb-8 text-center text-sm text-mist">Proof of skill, from the work you've already done.</p>
      <main id="main" className="w-full max-w-[440px]">
        <Outlet />
      </main>
    </div>
  );
}
