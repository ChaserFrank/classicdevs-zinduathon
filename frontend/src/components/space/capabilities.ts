import { prefersReducedMotion } from "@/lib/utils";

/** WebGL2 and more than 4 cores, or we show the static planet (DESIGN.md §Fallbacks). */
export function canRender3D(): boolean {
  if (typeof window === "undefined") return false;
  if (prefersReducedMotion()) return false;
  if ((navigator.hardwareConcurrency ?? 8) <= 4) return false;
  if (new URLSearchParams(window.location.search).has("static-planet")) return false;
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}
