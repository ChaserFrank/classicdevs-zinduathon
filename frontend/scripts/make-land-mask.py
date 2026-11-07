"""Generate public/textures/land-mask.png: a 360×180 equirectangular land mask (white = land).

Source: Natural Earth 1:110m land (public domain), https://www.naturalearthdata.com/
Run once (needs Pillow):  python3 scripts/make-land-mask.py
The SignalPlanet samples this mask to keep only lattice points that fall on land.
"""

import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"
OUT = Path(__file__).resolve().parent.parent / "public" / "textures" / "land-mask.png"
W, H, SCALE = 360, 180, 4  # draw at 4× and downsample for clean coastlines


def project(lon: float, lat: float) -> tuple[float, float]:
    return ((lon + 180) / 360 * W * SCALE, (90 - lat) / 180 * H * SCALE)


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as response:  # noqa: S310 - fixed public URL
        data = json.load(response)
    image = Image.new("L", (W * SCALE, H * SCALE), 0)
    draw = ImageDraw.Draw(image)
    for feature in data["features"]:
        geometry = feature["geometry"]
        polygons = (
            geometry["coordinates"]
            if geometry["type"] == "MultiPolygon"
            else [geometry["coordinates"]]
        )
        for polygon in polygons:
            outer, *holes = polygon
            draw.polygon([project(*p) for p in outer], fill=255)
            for hole in holes:
                draw.polygon([project(*p) for p in hole], fill=0)
    image = image.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, optimize=True)
    land = sum(1 for v in image.getdata() if v) / (W * H)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {land:.0%} land)")


if __name__ == "__main__":
    sys.exit(main())
