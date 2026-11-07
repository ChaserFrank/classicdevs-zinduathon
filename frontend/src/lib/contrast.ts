/** WCAG 2.x contrast maths, used by the glass readability tests (DESIGN.md §Readability guard). */
export type RGB = [number, number, number];

const channel = (c: number) => {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};

export function luminance([r, g, b]: RGB): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrast(a: RGB, b: RGB): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** A translucent layer over a background: the colour the eye actually sees. */
export function over(top: RGB, alpha: number, bottom: RGB): RGB {
  return top.map((c, i) => Math.round(c * alpha + (bottom[i] ?? 0) * (1 - alpha))) as RGB;
}

export const PALETTE = {
  void: [5, 5, 7] as RGB,
  flareHot: [255, 177, 92] as RGB, // brightest part of the rim: the worst case behind glass
  flare: [255, 122, 26] as RGB,
  ink: [245, 245, 247] as RGB,
  mist: [160, 160, 172] as RGB,
  glass: [18, 18, 24] as RGB,
  scrim: [12, 12, 17] as RGB,
};

export const GLASS_ALPHA = 0.55;
export const SCRIM_ALPHA = 0.84;
