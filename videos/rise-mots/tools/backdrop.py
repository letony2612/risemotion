"""The sky of the RISE site, as layers: soft blurred clouds (white for the sky, warm for the sunrise)
and the blurred cross. Seeded, so every run draws the same sky.
And the RISE logo (RISE_presentation/LOGO_3.png), without the stray hairline the file has under its R.
Usage: python3 tools/backdrop.py  -> assets/clouds_white.png, assets/clouds_warm.png, assets/cross.png, assets/rise_logo.png
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
W, H, M = 1080, 1920, 100  # frame, and the margin the clouds drift into


def clouds():
    rng = np.random.default_rng(7)
    w, h = W + 2 * M, H + 2 * M

    def octave(cell):
        g = rng.random((h // cell + 3, w // cell + 3))
        im = Image.fromarray((g * 255).astype(np.uint8)).resize(((w // cell + 3) * cell, (h // cell + 3) * cell), Image.BICUBIC)
        return np.asarray(im).astype(float)[:h, :w] / 255

    n = sum(k * octave(c) for c, k in ((480, 0.5), (240, 0.25), (120, 0.15), (60, 0.1)))
    n = (n - n.min()) / (n.max() - n.min())
    alpha = np.clip((n - 0.42) / 0.38, 0, 1) ** 1.3
    a = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(28))
    for name, rgb in (("clouds_white", (255, 255, 255)), ("clouds_warm", (255, 238, 214))):
        im = Image.new("RGBA", (w, h), rgb + (0,))
        im.putalpha(a)
        im.save(ROOT / "assets" / f"{name}.png")


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
    a = np.maximum(np.asarray(m), np.asarray(halo))
    im = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    im.save(ROOT / "assets" / "cross.png")


def logo():
    im = Image.open(ROOT.parents[1] / "RISE_presentation" / "LOGO_3.png").convert("RGBA")
    a = np.asarray(im).copy()
    # below the letters' baseline only the S's tail goes on (x 400-500): anything left of it is the hairline
    base = max(y for y in range(a.shape[0]) if (a[y, :390, 3] > 10).sum() > 200)
    a[base + 1:, :390, 3] = 0
    Image.fromarray(a).save(ROOT / "assets" / "rise_logo.png")


if __name__ == "__main__":
    clouds()
    cross()
    logo()
    print("clouds, cross and logo written")
