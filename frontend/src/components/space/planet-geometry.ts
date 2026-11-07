/**
 * Pure geometry for the Signal Planet, kept out of the React scene so it can be unit tested.
 */

export const KENYA = { lat: 0.0, lon: 37.9 };
export const NAIROBI = { lat: -1.29, lon: 36.82 };

/** Longitude that faces the camera (+z) at load: Kenya. */
export const FACING_LON = KENYA.lon;

export type Vec3 = [number, number, number];

/** lat/lon in degrees → unit vector, rotated so FACING_LON points at +z (the viewer). */
export function latLonToVec(lat: number, lon: number, facingLon = FACING_LON): Vec3 {
  const phi = (lat * Math.PI) / 180;
  const lambda = ((lon - facingLon) * Math.PI) / 180;
  return [Math.cos(phi) * Math.sin(lambda), Math.sin(phi), Math.cos(phi) * Math.cos(lambda)];
}

/** Inverse of latLonToVec for a unit vector. */
export function vecToLatLon([x, y, z]: Vec3, facingLon = FACING_LON): { lat: number; lon: number } {
  const lat = (Math.asin(Math.max(-1, Math.min(1, y))) * 180) / Math.PI;
  let lon = (Math.atan2(x, z) * 180) / Math.PI + facingLon;
  if (lon > 180) lon -= 360;
  if (lon < -180) lon += 360;
  return { lat, lon };
}

/** Evenly spread points on a sphere (golden-angle spiral). */
export function fibonacciSphere(count: number): Vec3[] {
  const points: Vec3[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = golden * i;
    points.push([Math.cos(theta) * radius, y, Math.sin(theta) * radius]);
  }
  return points;
}

/** A land mask lookup: true when (lat, lon) is land. The mask is equirectangular, width × height. */
export type LandMask = { width: number; height: number; data: Uint8ClampedArray };

export function isLand(mask: LandMask, lat: number, lon: number): boolean {
  const x = Math.min(mask.width - 1, Math.max(0, Math.floor(((lon + 180) / 360) * mask.width)));
  const y = Math.min(mask.height - 1, Math.max(0, Math.floor(((90 - lat) / 180) * mask.height)));
  return (mask.data[(y * mask.width + x) * 4] ?? 0) > 127; // red channel of RGBA
}

/** Lattice points that fall on land (Antarctica trimmed: it would crowd the hidden south pole). */
export function landPoints(mask: LandMask, count: number): Vec3[] {
  return fibonacciSphere(count).filter((p) => {
    const { lat, lon } = vecToLatLon(p);
    return lat > -62 && isLand(mask, lat, lon);
  });
}

/** Deterministic pseudo-random numbers so the scene is identical on every load (and in tests). */
export function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export const easeOutCubic = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
