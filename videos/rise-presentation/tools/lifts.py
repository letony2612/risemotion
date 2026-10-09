"""Pieces of the app screens that lift out of the phone (cut from the real captures).

Each entry: the capture shown on the phone screen, the piece's box in its 1080x2400 pixels, and an
optional patch painted with the page colour (e.g. a floating button that overlaps the piece).
build.py places every piece exactly over its spot on the screen, so it lifts off its own pixels.
Usage: python3 tools/lifts.py  -> assets/lift/<name>.png
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT.parent.parent / "RISE_presentation" / "1_captures_clair"
OUT = ROOT / "assets" / "lift"
PAGE = (250, 248, 245)

LIFTS = {
    # feed: Sarah's testimony ("Dieu est fidèle"), the + button painted out
    "post_sarah": ("02_accueil.png", (0, 1596, 1080, 2000), (880, 340, 1080, 404)),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cap, box, patch) in LIFTS.items():
        im = Image.open(CAP / cap).convert("RGB").crop(box)
        if patch:
            im.paste(PAGE, patch)
        im.save(OUT / f"{name}.png")
        print(name, im.size)


if __name__ == "__main__":
    main()
