import { contrast, GLASS_ALPHA, over, PALETTE, SCRIM_ALPHA } from "./contrast";

const AA = 4.5;

describe("text contrast on glass (WCAG AA)", () => {
  const glassOnVoid = over(PALETTE.glass, GLASS_ALPHA, PALETTE.void);
  const glassOnRim = over(PALETTE.glass, GLASS_ALPHA, PALETTE.flareHot);
  const scrimOnRim = over(PALETTE.scrim, SCRIM_ALPHA, PALETTE.flareHot);

  it("ink and mist pass on glass over empty space", () => {
    expect(contrast(PALETTE.ink, glassOnVoid)).toBeGreaterThan(AA);
    expect(contrast(PALETTE.mist, glassOnVoid)).toBeGreaterThan(AA);
  });

  it("default glass over the brightest rim fails for mist — so it must never sit there", () => {
    expect(contrast(PALETTE.mist, glassOnRim)).toBeLessThan(AA);
  });

  it("scrim glass over the brightest rim passes for ink and mist", () => {
    expect(contrast(PALETTE.ink, scrimOnRim)).toBeGreaterThan(AA);
    expect(contrast(PALETTE.mist, scrimOnRim)).toBeGreaterThan(AA);
  });

  it("primary buttons (black on flare) pass", () => {
    expect(contrast([0, 0, 0], PALETTE.flare)).toBeGreaterThan(AA);
  });

  it("mist directly on the page background passes", () => {
    expect(contrast(PALETTE.mist, PALETTE.void)).toBeGreaterThan(AA);
  });
});
