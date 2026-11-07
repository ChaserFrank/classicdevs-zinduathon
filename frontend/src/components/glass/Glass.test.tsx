import { render, screen } from "@testing-library/react";

import { GlassPanel, GlassPill } from "./Glass";

describe("glass components", () => {
  it("renders the requested tag and the scrim variant", () => {
    render(
      <GlassPanel as="section" aria-label="Login" scrim glow>
        Hello
      </GlassPanel>,
    );
    const panel = screen.getByRole("region", { name: "Login" });
    expect(panel.tagName).toBe("SECTION");
    expect(panel.className).toContain("glass-scrim");
  });

  it("pills are rounded glass", () => {
    render(<GlassPill>Badge</GlassPill>);
    expect(screen.getByText("Badge").className).toContain("glass-pill");
  });
});
