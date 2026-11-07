import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes: later classes win over earlier ones (e.g. a caller's padding). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}
