"""Convert the captured planet PNG to a transparent WebP.

The capture is opaque (bloom post-processing renders to an opaque buffer), so we derive alpha from
brightness: black space becomes transparent, the glow keeps its colour. Then crop to content.
"""
from pathlib import Path

from PIL import Image

src = Path("public/images/planet-static.png")
rgb = Image.open(src).convert("RGB")
px = rgb.load()
out = Image.new("RGBA", rgb.size)
po = out.load()
W, H = rgb.size
for y in range(H):
    for x in range(W):
        r, g, b = px[x, y]
        m = max(r, g, b)
        a = min(255, max(0, (m - 8) * 3))  # values ≤ 8 are background noise
        if a == 0:
            po[x, y] = (0, 0, 0, 0)
        else:
            k = 255 / max(a, 1)
            po[x, y] = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), a)
bbox = out.getchannel("A").getbbox()
if bbox:
    out = out.crop(bbox)
out.save("public/images/planet-static.webp", "WEBP", quality=84, method=6)
src.unlink()
print("saved public/images/planet-static.webp", out.size)
