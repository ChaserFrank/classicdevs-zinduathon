import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { canRender3D } from "./capabilities";

const Scene = lazy(() => import("./SignalPlanetScene"));

/** The pre-rendered planet with a CSS glow: reduced motion, low-power devices, and while 3D loads. */
export function StaticPlanet({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <div className="absolute left-1/2 top-[58%] h-[min(130vw,1100px)] w-[min(130vw,1100px)] -translate-x-1/2 rounded-full bg-flare/25 blur-[90px]" />
      <img
        src="/images/planet-static.webp"
        alt=""
        className="absolute bottom-0 left-1/2 w-[min(150vw,1500px)] max-w-none -translate-x-1/2 select-none"
        draggable={false}
      />
    </div>
  );
}

type Props = {
  className?: string;
  /** Play the noise → signal intro (landing page, first load only). */
  intro?: boolean;
  onIntroDone?: () => void;
};

/**
 * Chooses 3D or static, lazy-loads the scene, and pauses rendering when the tab is hidden or the
 * planet is scrolled out of view (keeps laptops cool and the main thread free).
 */
export function SignalPlanet({ className, intro = false, onIntroDone }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [use3D] = useState(canRender3D);
  const [visible, setVisible] = useState(true);
  const [tabVisible, setTabVisible] = useState(() => document.visibilityState !== "hidden");

  useEffect(() => {
    if (!use3D) onIntroDone?.(); // nothing to wait for
  }, [use3D, onIntroDone]);

  useEffect(() => {
    const onVisibility = () => setTabVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    const el = host.current;
    const observer =
      el && "IntersectionObserver" in window
        ? new IntersectionObserver(([entry]) => setVisible(Boolean(entry?.isIntersecting)))
        : null;
    if (el && observer) observer.observe(el);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, []);

  return (
    <div ref={host} aria-hidden className={cn("pointer-events-none absolute inset-0", className)}>
      {use3D ? (
        <Suspense fallback={<StaticPlanet />}>
          <Scene intro={intro} onIntroDone={onIntroDone} paused={!visible || !tabVisible} />
        </Suspense>
      ) : (
        <StaticPlanet />
      )}
    </div>
  );
}
