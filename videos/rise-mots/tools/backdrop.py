"""The two lights the reel flips between, each one frame, still, like the reference's backgrounds:
- the sky of the RISE site: light blue, soft blurred clouds, the blurred white cross behind the words;
- dusk: the same sky at evening, grey with a periwinkle light (the reference's second colour), where
  the clouds and the cross are only a trace.
And the RISE logo (RISE_presentation/LOGO_3.png), without the stray hairline the file has under its R.
Seeded, so every run draws the same sky.
Usage: python3 tools/backdrop.py  -> assets/sky.png, assets/dusk.png, assets/rise_logo.png
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1920
Y, X = np.mgrid[0:H, 0:W].astype(float)


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def vertical(stops):
    """A top-to-bottom gradient through (position 0-1, colour) stops."""
    t = Y / (H - 1)
    out = np.zeros((H, W, 3))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        k = ((t - p0) / (p1 - p0))[..., None]
        out = np.where(m[..., None], hexrgb(c0) * (1 - k) + hexrgb(c1) * k, out)
    return out


def glow(cx, cy, rx, ry):
    """A soft elliptical light, 1 at its centre, 0 at its rim."""
    d = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
    return np.clip(1 - d, 0, 1) ** 1.6


def clouds():
    """Soft blurred clouds: low-frequency noise, kept to the bottom and the top corners so the
    middle band, where the words sit, stays clear sky."""
    rng = np.random.default_rng(7)

    def octave(cell):
        g = rng.random((H // cell + 3, W // cell + 3))
        im = Image.fromarray((g * 255).astype(np.uint8)).resize(((W // cell + 3) * cell, (H // cell + 3) * cell), Image.BICUBIC)
        return np.asarray(im).astype(float)[:H, :W] / 255

    n = sum(k * octave(c) for c, k in ((480, 0.55), (240, 0.3), (120, 0.15)))
    n = (n - n.min()) / (n.max() - n.min())
    a = np.clip((n - 0.4) / 0.4, 0, 1) ** 1.4
    t = Y / (H - 1)
    band = np.clip(np.abs(t - 0.47) / 0.3, 0, 1) ** 1.5  # 0 in the words' band, 1 towards top and bottom
    a = a * (0.25 + 0.75 * band)
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(44))).astype(float) / 255
    return a


def cross():
    """A white cross, blurred into light, with a soft halo where the arms meet."""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((470, 260, 610, 1510), 20, fill=255)
    d.rounded_rectangle((250, 560, 830, 690), 20, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(38))
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse((300, 330, 780, 930), fill=140)
    halo = halo.filter(ImageFilter.GaussianBlur(90))
    return np.maximum(np.asarray(m), np.asarray(halo)).astype(float) / 255


def over(base, rgb, alpha):
    return base * (1 - alpha[..., None]) + np.asarray(rgb, float) * alpha[..., None]


def save(a, name):
    Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8)).save(ROOT / "assets" / name, optimize=True)


def main():
    c, x = clouds(), cross()
    white = (255, 255, 255)
    # the RISE sky: deeper blue overhead, paler towards the horizon
    sky = vertical([(0, "#93cdef"), (0.55, "#bfe3f6"), (1, "#def1fb")])
    sky = over(sky, white, 0.85 * c)
    sky = over(sky, white, 0.92 * x)
    save(sky, "sky.png")
    # dusk: light grey overhead going to a deep grey-blue, a periwinkle light from the top right
    dusk = vertical([(0, "#d0d1d7"), (0.28, "#9597a3"), (0.5, "#727480"), (1, "#66676f")])
    dusk = over(dusk, hexrgb("#95a0e0"), 0.95 * glow(1080, 150, 1150, 1100))
    dusk = over(dusk, hexrgb("#8a8fc8"), 0.5 * glow(1080, 1000, 800, 700))
    dusk = over(dusk, white, 0.1 * c)
    dusk = over(dusk, white, 0.07 * x)
    save(dusk, "dusk.png")


def logo():
    im = Image.open(ROOT.parents[1] / "RISE_presentation" / "LOGO_3.png").convert("RGBA")
    a = np.asarray(im).copy()
    # below the letters' baseline only the S's tail goes on (x 400-500): anything left of it is the hairline
    base = max(y for y in range(a.shape[0]) if (a[y, :390, 3] > 10).sum() > 200)
    a[base + 1:, :390, 3] = 0
    Image.fromarray(a).save(ROOT / "assets" / "rise_logo.png")


if __name__ == "__main__":
    main()
    logo()
    print("sky, dusk and logo written")
