# Design

The look comes from one reference image, `frontend-prompt/design-reference/01-landing-reference.png`
(a dark "global network" hero with a glowing dotted planet). We adapt its **aesthetic and motion**,
never its brand: no logo, names, wording or product names from it. There are no login or
registration references, so the auth screens use the guidelines' layout (§1.6).

## What the reference does

| Element  | Reference                                                                                                               | What we take                                                   | What we change                                                                                  |
| -------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Page     | Near-black field, generous empty space                                                                                  | Same                                                           | Our `void` `#050507` (sampled `#060606`–`#070709`)                                              |
| Nav      | Floating pill, centred, logo in an orange rounded square, links with chevrons, white "Sign up" pill on the right        | Same structure                                                 | Our links (How it works, Scoring, For recruiters, Privacy), our glyph, "Get your skill card"    |
| Badge    | Small dark pill with an orange icon above the headline                                                                  | Same                                                           | "Proof of skill for the AI era" with a glowing dot                                              |
| Headline | Bold geometric sans, white, centred, two lines                                                                          | Same proportions (clamp 2.4–4.5rem, −0.02em, line-height 1.05) | Plus Jakarta Sans 700; our copy                                                                 |
| Sub-line | Muted grey, two short lines                                                                                             | Same                                                           | `mist` raised to `#A0A0AC` for AA contrast                                                      |
| Planet   | Huge sphere rising from the bottom (top ~60% down), dotted world map, burning orange rim with a soft bloom, faint stars | Same                                                           | Dots form Africa with Kenya facing the viewer; a Nairobi pulse; a one-time noise → signal intro |

### Sampled colours (and why the final tokens are brighter)

The reference is a **dimmed photo of a screen inside a frame**, so every colour samples darker than
the design it shows. Hues were matched, brightness restored:

| Where          | Sampled             | Hue  | Token                                     |
| -------------- | ------------------- | ---- | ----------------------------------------- |
| Rim, median    | `#94410D`           | 23°  | `ember` `#C2410C`                         |
| Rim, mid       | `#C97431`           | 24°  | `flare` `#FF7A1A`                         |
| Rim, brightest | `#E09155`           | 26°  | `flare-hot` `#FFB15C`                     |
| Planet body    | `#15051C`           | 284° | `planet` `#170A28` → `planet-2` `#2A1745` |
| Page           | `#060606`–`#070709` | –    | `void` `#050507`                          |
| Sign-up pill   | `#F6F6F6`           | –    | `ink` `#F5F5F7` (white CTA pill)          |

All tokens live in `src/styles/tokens.css` (as `R G B` so Tailwind can add alpha).

## Glass

Dark smoked glass, so the orange glow and the dots bleed through.

| Tier               | Use                                                             | Recipe                                                                                                             |
| ------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `GlassPanel`       | Main floating surfaces                                          | `rgba(18,18,24,0.55)`, blur 24px + saturate 160%, 1px `line` border, inner top highlight, 24px radius, deep shadow |
| `GlassPanel scrim` | Surfaces that can sit over the planet's rim (auth, error pages) | `rgba(12,12,17,0.84)`                                                                                              |
| `GlassCard`        | Inside panels                                                   | `rgba(255,255,255,0.04)`, blur 12px, 16px radius                                                                   |
| `GlassPill`        | Nav, badges, chips, filters                                     | `rgba(20,20,26,0.7)`, blur 8px, fully rounded                                                                      |
| `glow`             | One per screen                                                  | Blurred radial `flare` bloom at ~30% + a 1px edge from `flare-hot` to transparent (`LitEdge`)                      |
| Fallback           | No `backdrop-filter`                                            | Solid `void-2` at 92%                                                                                              |

### Readability guard (tested in `src/lib/contrast.test.ts`)

| Text on…                                           | `ink`  | `mist`    | Verdict                                                     |
| -------------------------------------------------- | ------ | --------- | ----------------------------------------------------------- |
| Glass over empty space                             | 17.9:1 | 7.5:1     | AA ✓                                                        |
| Default glass over the brightest rim (`flare-hot`) | 5.7:1  | **2.4:1** | `mist` fails, so default glass is never placed over the rim |
| Scrim glass over the brightest rim                 | 13.4:1 | 5.7:1     | AA ✓                                                        |
| Black on `flare` (primary button)                  | 8.1:1  | –         | AA ✓                                                        |
| `mist` directly on the page                        | –      | 7.9:1     | AA ✓                                                        |

## Signal Planet (`src/components/space/`)

- **Dots:** 16,000-point Fibonacci lattice, kept where `public/textures/land-mask.png` is land
  (360×180 equirectangular mask generated from Natural Earth 1:110m by
  `scripts/make-land-mask.py`; Antarctica trimmed). ~5,000 dots, white at 85%, sizes 2.2–3.6.
- **Body:** dark violet sphere with an inner fresnel band (`ember` → `flare`, hotter at the very edge).
- **Outer glow:** a camera-facing disc behind the planet with exponential falloff and dithering
  (a fresnel shell gave visible banding rings), plus a low-intensity `Bloom`.
- **Orientation:** Kenya faces the viewer at load (the sphere is tilted toward the camera so the
  equator rises into the visible cap). One turn per 4 minutes. An amber ring pulses at Nairobi every 4 s.
- **Framing:** only the top ~40% of the sphere shows. Wide screens: diameter ≈ 60% of the width.
  Portrait phones: the camera pulls back and rises so the planet spans ~115% of the width and
  still only its cap shows.
- **Noise → signal:** on the first visit of a session, ~1,500 dots start scattered in `mist` and
  drift onto the planet over 2.4 s (ease-out), turning white; then the badge, headline (40 ms word
  stagger), sub-line and buttons fade up. That is the only orchestrated sequence.
- **Stars:** 420 points, slow twinkle, pointer parallax (a few px).

### Fallbacks and performance

| Situation                                                               | What renders                                                                                                                                                        |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prefers-reduced-motion`, ≤ 4 CPU cores, no WebGL2, or `?static-planet` | `public/images/planet-static.webp` (rendered from the same scene by `scripts/capture-static-planet.mjs` + `scripts/to-webp.py`, brightness → alpha) with a CSS glow |
| While the 3D chunk loads                                                | The same static image                                                                                                                                               |
| Tab hidden or planet scrolled off-screen                                | Rendering paused (`frameloop="never"`)                                                                                                                              |

- three.js is a separate lazy chunk (≈ 300 kB gzipped), loaded only on the landing and auth screens;
  the app core is ≈ 60 kB gzipped.
- Device pixel ratio is capped at 1.75.
- **fps:** headless CI renders WebGL in software (SwiftShader), so frame rates there aren't
  meaningful. Measure on a real mid-range laptop with Chrome DevTools → Performance → Frames
  (target 60 fps) and record it here. _(Pending a run on a physical device.)_

## In-app backdrop

`SpaceBackdrop`: near-black, a planet just out of frame at the top right (only its rim shows as a
soft arc), faint star dust, 4% grain. No WebGL. `ProgressGlow` (steps 1–4 of an analysis) raises
the arc's brightness; it settles when the card appears (step 5).

## Motion rules

- Framer Motion for the hero sequence and user-triggered moments; CSS transitions elsewhere.
- 150–400 ms, except the hero sequence.
- No looping hover animations. Toasts slide from the top centre as glass pills.
- Everything respects `prefers-reduced-motion` (static planet, no sequence, near-instant transitions).

## Type

Plus Jakarta Sans (self-hosted via `@fontsource`): 700 headlines, 400/500/600 UI. Headlines tight
(−0.02em, line-height 1.05), centred in heroes, left-aligned in the app. Scores use tabular
figures (`.tabular`). Sentence case everywhere.
