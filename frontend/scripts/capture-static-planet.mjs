// Renders the real 3D planet in headless Chromium and saves public/images/planet-static.png
// (converted to .webp by scripts/to-webp.py). Run with the dev server up:  node scripts/capture-static-planet.mjs
import { chromium } from "@playwright/test";

const url = process.env.CAPTURE_URL ?? "http://localhost:5173/dev/planet-capture";
const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(4000); // mask decode + first frames + bloom
await page
  .locator('[data-testid="planet-capture"]')
  .screenshot({ path: "public/images/planet-static.png", omitBackground: true });
await browser.close();
console.log("saved public/images/planet-static.png");
