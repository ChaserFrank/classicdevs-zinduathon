import {
  easeOutCubic,
  fibonacciSphere,
  isLand,
  landPoints,
  latLonToVec,
  seeded,
  vecToLatLon,
  type LandMask,
} from "./planet-geometry";

/** 360×180 mask: land only in the eastern hemisphere's tropics (a crude "Africa"). */
function mask(): LandMask {
  const width = 360;
  const height = 180;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const lon = x - 180;
      const lat = 90 - y;
      if (lon > 0 && lon < 50 && Math.abs(lat) < 30) data[(y * width + x) * 4] = 255;
    }
  return { width, height, data };
}

describe("planet geometry", () => {
  it("puts Kenya in front of the viewer at load", () => {
    const [x, y, z] = latLonToVec(0, 37.9);
    expect(x).toBeCloseTo(0);
    expect(y).toBeCloseTo(0);
    expect(z).toBeCloseTo(1);
  });

  it("round-trips lat/lon", () => {
    const { lat, lon } = vecToLatLon(latLonToVec(-1.29, 36.82));
    expect(lat).toBeCloseTo(-1.29);
    expect(lon).toBeCloseTo(36.82);
    expect(vecToLatLon(latLonToVec(10, -170)).lon).toBeCloseTo(-170);
  });

  it("spreads lattice points on the unit sphere", () => {
    const points = fibonacciSphere(500);
    expect(points).toHaveLength(500);
    points.forEach((p) => expect(Math.hypot(...p)).toBeCloseTo(1));
  });

  it("keeps only points over land", () => {
    const m = mask();
    expect(isLand(m, 0, 20)).toBe(true);
    expect(isLand(m, 0, -40)).toBe(false);
    const land = landPoints(m, 4000);
    expect(land.length).toBeGreaterThan(50);
    land.forEach((p) => expect(isLand(m, vecToLatLon(p).lat, vecToLatLon(p).lon)).toBe(true));
  });

  it("is deterministic", () => {
    const a = seeded(1);
    const b = seeded(1);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("eases and clamps", () => {
    expect(easeOutCubic(-1)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(2)).toBe(1);
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
  });
});
