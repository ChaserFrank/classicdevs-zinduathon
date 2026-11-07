/**
 * Captures every route at 390 px and 1440 px into e2e/__screenshots__/ for human review
 * (not snapshot assertions). Run: npm run screenshots
 */
import { test, type Page } from "@playwright/test";

const WIDTHS = [
  { name: "390", width: 390, height: 844 },
  { name: "1440", width: 1440, height: 900 },
];

type Shot = { name: string; path: string; ready?: (page: Page) => Promise<void> };

const SHOTS: Shot[] = [
  { name: "landing", path: "/", ready: (p) => p.waitForTimeout(8000) }, // intro + reveal (slow under software WebGL)
  {
    name: "dev-ui",
    path: "/dev/ui",
    ready: async (p) => {
      await p
        .getByTestId("health-result")
        .getByText(/Reached the API|couldn't reach/)
        .waitFor();
      await p.waitForTimeout(1500);
    },
  },
  { name: "login-layout", path: "/login", ready: (p) => p.waitForTimeout(2500) },
  { name: "app-shell", path: "/app", ready: (p) => p.waitForTimeout(800) },
  { name: "not-found", path: "/this-does-not-exist", ready: (p) => p.waitForTimeout(800) },
];

for (const size of WIDTHS) {
  for (const shot of SHOTS) {
    test(`${shot.name} @ ${size.name}`, async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto(shot.path, { waitUntil: "networkidle" });
      await shot.ready?.(page);
      await page.screenshot({
        path: `e2e/__screenshots__/${shot.name}-${size.name}.png`,
        fullPage: shot.name === "dev-ui",
      });
    });
  }
}
