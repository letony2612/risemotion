"""Cut the RISE app screenshots into individual UI elements for the motion design.

Every element comes from the real app captures in RISE_presentation/ (demo
members only). Coordinates are in the original 1080x2400 screen pixels.
Usage: python3 tools/prepare_assets.py <scratch_dir_with_video_frames>
"""
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent.parent / "RISE_presentation"
CAP = SRC / "1_captures_clair"
OUT = ROOT / "assets" / "ui"
OUT.mkdir(parents=True, exist_ok=True)
FRAMES = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def img(name):
    if name.startswith("frame:"):
        return Image.open(FRAMES / name[6:]).convert("RGBA")
    return Image.open(CAP / name).convert("RGBA")


def crop(src, box, out, fill=None):
    im = img(src).crop(box)
    if fill:
        # paint over an overlapping widget (e.g. the floating + button)
        px = im.load()
        (x0, y0, x1, y1), color = fill
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = color
    im.save(OUT / out)
    return im


def key_background(im, tol=10):
    """Make the flat page background transparent (flood fill from the borders)."""
    a = np.array(im).astype(int)
    h, w = a.shape[:2]
    bg = a[2, 2, :3]
    mask = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        q.append((0, x)); q.append((h - 1, x))
    for y in range(h):
        q.append((y, 0)); q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        if mask[y, x]:
            continue
        if np.abs(a[y, x, :3] - bg).max() > tol:
            continue
        mask[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx]:
                q.append((ny, nx))
    out = np.array(im)
    out[mask, 3] = 0
    return Image.fromarray(out)


# ---------- feed ----------
crop("frame:fil_55.png", (34, 140, 1058, 551), "post_temoignage.png")
crop("frame:fil_55.png", (34, 600, 1058, 1250), "post_verset.png")
crop("02_accueil.png", (0, 338, 1080, 468), "confier_row.png")
crop("21_profil.png", (172, 1170, 1046, 1834), "photo_louange.png")
crop("04_publier.png", (820, 150, 1062, 258), "btn_publier.png")

# ---------- prayer ----------
crop("06_priere.png", (40, 349, 1036, 945), "prayer_maman.png")
crop("06_priere.png", (90, 821, 266, 905), "btn_jeprie.png")
crop("07_priere_detail.png", (52, 1159, 1035, 1323), "upd_sarah.png")
crop("07_priere_detail.png", (52, 1422, 1035, 1602), "upd_esther.png")
crop("09_confier_une_priere.png", (74, 2149, 1006, 2284), "btn_confier.png")
crop("08_priere_exaucee.png", (30, 335, 1050, 1020), "card_exaucee.png")
crop("08_priere_exaucee.png", (770, 410, 930, 472), "badge_exaucee.png")
crop("03_post_commentaires.png", (34, 1255, 1046, 1409), "com_david.png")
crop("03_post_commentaires.png", (34, 1433, 1046, 1584), "com_esther.png")
crop("03_post_commentaires.png", (34, 1609, 1046, 1760), "com_rebecca.png")
crop("22_notifications.png", (0, 1024, 1080, 1204), "notif_exaucee.png")
crop("22_notifications.png", (0, 1238, 1080, 1382), "notif_like.png")

# ---------- groups & messages ----------
for i, (y0, y1) in enumerate([(410, 576), (608, 774), (803, 970), (1001, 1168), (1197, 1364)], 1):
    crop("10_groupes.png", (0, y0, 1080, y1), f"group_{i}.png")
bubbles = [
    ("b1", (30, 1222, 900, 1377)),
    ("b2", (225, 1400, 1056, 1503)),
    ("b3", (30, 1530, 900, 1688)),
    ("b4", (225, 1706, 1056, 1811)),
    ("b5", (30, 1834, 900, 1935)),
    ("b6", (560, 1958, 1056, 2060)),
]
for name, box in bubbles:
    # kept on the page colour (#FAF8F5): they sit on a paper chat panel
    img("13_conversation.png").crop(box).save(OUT / f"bubble_{name}.png")

# ---------- quiz ----------
crop("15_quiz_parcours.png", (40, 308, 1040, 875), "quiz_stats.png")
crop("frame:q_unsel.png", (52, 315, 1013, 551), "quiz_question.png")
for i, (y0, y1) in enumerate([(623, 770), (799, 943), (972, 1116), (1145, 1289)], 1):
    crop("frame:q_unsel.png", (52, y0, 1029, y1), f"answer_{i}.png")
crop("17_quiz_question.png", (52, 623, 1029, 770), "answer_1_sel.png")
crop("18_quiz_reponse.png", (52, 623, 1029, 770), "answer_1_ok.png")
crop("18_quiz_reponse.png", (0, 1676, 1080, 2138), "quiz_exact.png")
crop("20_quiz_resultat.png", (259, 742, 810, 905), "quiz_stars.png")
crop("20_quiz_resultat.png", (270, 1006, 810, 1170), "quiz_sansfaute.png")
for i, (x0, x1) in enumerate([(61, 365), (389, 691), (716, 1019)], 1):
    crop("20_quiz_resultat.png", (x0, 1233, x1, 1481), f"quiz_tile_{i}.png")

# ---------- buttons and badges: detour them from their flat background ----------
for name, tol in (("btn_publier", 12), ("btn_confier", 12), ("btn_jeprie", 4), ("badge_exaucee", 10)):
    key_background(Image.open(OUT / f"{name}.png").convert("RGBA"), tol).save(OUT / f"{name}.png")

# ---------- logo split: R / i stem / S / E / flame ----------
logo = Image.open(SRC / "LOGO_3.png").convert("RGBA")
L = np.array(logo)
H = L.shape[0]
colored = (L[:, :, 3] > 20) & ((L[:, :, 0].astype(int) - L[:, :, 2].astype(int)) > 60)
ys, xs = np.where(colored)
flame_bottom = ys.max()
parts = {"R": (0, 229), "i": (250, 325), "S": (341, 551), "E": (577, 767)}
for k, (x0, x1) in parts.items():
    part = L.copy()
    part[:, :x0, 3] = 0
    part[:, x1:, 3] = 0
    if k == "i":
        part[: flame_bottom + 3, :, 3] = 0  # stem only
    Image.fromarray(part).save(OUT / f"logo_{k}.png")
flame = L.copy()
flame[flame_bottom + 3:, :, 3] = 0
flame[:, :250, 3] = 0
flame[:, 325:, 3] = 0
Image.fromarray(flame).save(OUT / "logo_flame.png")
fl = Image.fromarray(flame).crop((246, 0, 330, flame_bottom + 4))
fl.save(OUT / "flame.png")
print("flame bottom", flame_bottom, "flame crop", fl.size)
print("ok", len(list(OUT.glob("*.png"))), "files")
