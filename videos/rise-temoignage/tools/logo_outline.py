"""The RISE logo as lines to draw: the outlines of its letters and of the flame on its I, traced once from the
official logo (the last frame of its splash animation, videos/rise-ugc/assets/brand/rise_splash_dark.webm), so
the episodes can draw the logo by hand, stroke by stroke, like everything else.
Needs contourpy (pip install contourpy), only to run this; the episodes read the JSON.
Usage: python3 tools/logo_outline.py  -> assets/rise_logo_outline.json
"""
import json
import subprocess
import tempfile
from pathlib import Path

import contourpy
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT.parents[1] / "videos/rise-ugc/assets/brand/rise_splash_dark.webm"
OUT = ROOT / "assets" / "rise_logo_outline.json"
WIDTH = 1000  # traced at this width; the JSON is in units of the logo's width


def contours(mask, min_len=24, step=3):
    gen = contourpy.contour_generator(z=np.pad(mask, 2).astype(float), line_type="Separate")
    out = []
    for c in gen.lines(0.5):
        if len(c) < min_len:
            continue
        c = c[::step] - 2  # back from the padding
        out.append([[round(x / WIDTH, 5), round(y / WIDTH, 5)] for x, y in c])
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-ss", "5.0", "-i", str(SPLASH), "-frames:v", "1", f"{d}/l.png"], check=True)
        im = Image.open(f"{d}/l.png").convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 140 else 0).getbbox())
    im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    rgb, alpha = a[..., :3], a[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / (mx + 1e-6)
    flame = (alpha > 150) & (sat > 0.35)
    letters = (alpha > 128) & (sat <= 0.35)
    data = {"aspect": im.height / WIDTH, "letters": contours(letters), "flame": contours(flame, 12, 2)}
    OUT.write_text(json.dumps(data))
    print(f"{OUT.relative_to(ROOT)}: {len(data['letters'])} letter outlines, {len(data['flame'])} flame outlines, aspect {data['aspect']:.3f}")


if __name__ == "__main__":
    main()
