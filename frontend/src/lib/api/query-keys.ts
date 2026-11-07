/** Every TanStack Query key in one place, so invalidation after mutations stays precise. */
export const qk = {
  health: ["health"] as const,
  me: ["me"] as const,
};
