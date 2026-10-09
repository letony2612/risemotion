"""Pieces of the app screens that lift out of the phone (cut from the real captures).

Each entry: the capture shown on the phone screen, the piece's box in its 1080x2400 pixels, and an
optional patch painted with the page colour (e.g. a floating button that overlaps the piece).
build.py places every piece exactly over its spot on the screen, so it lifts off its own pixels.
Pieces in SHEETS are floating sheets captured over the app's own dimmed backdrop: everything outside
their rounded outline is made transparent (the video dims the screen behind them itself).
Usage: python3 tools/lifts.py            -> assets/lift/<name>.png
       python3 tools/lifts.py --lang en  -> assets/lift_en/<name>.png, from the English captures
"""
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LANG = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else os.environ.get("RISE_LANG", "fr")
SUFFIX = "" if LANG == "fr" else f"_{LANG}"
CAP = ROOT.parent.parent / "RISE_presentation" / f"1_captures_clair{SUFFIX}"
OUT = ROOT / "assets" / f"lift{SUFFIX}"
PAGE = (250, 248, 245)

LIFTS = {
    # intro, floating: the composer (sharing), the messages (meeting), the quiz streak is in assets/ui
    "composer": ("04_publier.png", (0, 180, 1080, 975), None),
    "messages": ("12_messages.png", (0, 395, 1080, 1365), None),
    # feed: the prompt ("une question"), Sarah's testimony (the + button painted out)
    "feed_prompt": ("02_accueil.png", (0, 330, 1080, 470), None),
    "post_sarah": ("02_accueil.png", (0, 1596, 1080, 2000), (880, 340, 1080, 404)),
    # groups, and what their members say (floating beside the phone)
    "group_1": ("10_groupes.png", (0, 410, 1080, 576), None),
    "group_2": ("10_groupes.png", (0, 608, 1080, 774), None),
    "group_3": ("10_groupes.png", (0, 803, 1080, 970), None),
    "group_4": ("10_groupes.png", (0, 1001, 1080, 1168), None),
    "chat_caleb": ("11_groupe_discussion.png", (20, 700, 800, 960), None),
    "chat_deborah": ("11_groupe_discussion.png", (20, 975, 800, 1175), None),
    "chat_me": ("11_groupe_discussion.png", (300, 1190, 1060, 1360), None),
    "chat_jonathan": ("11_groupe_discussion.png", (20, 1410, 800, 1610), None),
    # prayers: Rebecca's request for her mother, the sheet to share a request
    "prayer_maman": ("06_priere.png", (40, 349, 1036, 945), None),
    "confier_sheet": ("09_confier_une_priere.png", (0, 720, 1080, 2400), None),
    # explorer: the verse of the day
    "verse": ("14_explorer.png", (40, 215, 1040, 905), None),
    # quiz: the first answer (its states are stacked from assets/ui), the "Exact !" sheet
    "quiz_answer": ("17_quiz_question.png", (52, 623, 1029, 770), None),
    "quiz_exact": ("18_quiz_reponse.png", (0, 1660, 1080, 2330), None),
}
SHEETS = {"confier_sheet"}


def sheet_cutout(im):
    """RGBA: the sheet's rounded rectangle, found on its bright surface, with an anti-aliased edge; the
    dimmed backdrop around it transparent, and the rim (a blend of sheet and backdrop) repainted with the
    sheet's own colour so no dark line is left."""
    a = np.asarray(im).astype(float)
    lum = a.mean(axis=2)
    h, w = lum.shape
    bright = lum > 170
    xs = np.where(bright[h // 2])[0]
    x0, x1 = xs.min(), xs.max() + 1
    y0 = 0
    # the corner radius from the left edge's inset near the top: r = (o + d) + sqrt(2 o d)
    radii = []
    for d in range(15, 45, 5):
        row = np.where(bright[y0 + d])[0]
        o = row.min() - x0
        if o > 0:
            radii.append(o + d + np.sqrt(2 * o * d))
    r = float(np.median(radii))
    # the bottom: the last sheet row in a column just past the corner (content in between does not matter)
    y1 = np.where(bright[:, int(x0 + r + 10)])[0].max() + 1
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    qx, qy = np.abs(xx - cx) - (hw - r), np.abs(yy - cy) - (hh - r)
    dist = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    alpha = np.clip(0.5 - dist, 0, 1)
    surface = np.median(a[(dist < -6) & (dist > -12) & bright], axis=0)
    rim = dist > -3
    a[rim] = surface
    out = np.dstack([a, alpha * 255]).round().astype(np.uint8)
    print(f"  sheet {x0}-{x1} x {y0}-{y1}, corner radius {r:.0f}, surface {surface.round()}")
    return Image.fromarray(out, "RGBA")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cap, box, patch) in LIFTS.items():
        im = Image.open(CAP / cap).convert("RGB").crop(box)
        if patch:
            im.paste(PAGE, patch)
        if name in SHEETS:
            im = sheet_cutout(im)
        im.save(OUT / f"{name}.png")
        print(name, im.size)


if __name__ == "__main__":
    main()
