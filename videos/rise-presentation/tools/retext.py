"""Hand-made English versions of the app screens whose text sits on flat UI (the quiz, a verse post).

The other English captures were translated with an AI image edit (see RISE_presentation/1_captures_clair_en);
these ones are re-typeset instead, which keeps every pixel that is not text. For each French line:
  1. the line's box is erased by solving Laplace's equation from the pixels around it (right for flat
     fills, gradients and the blurred sky of the quiz path alike);
  2. the French is re-rendered in the app's own fonts (Inter, and Newsreader for titles and verses) and
     its size fitted to the original ink, which also fixes where the line's box sits;
  3. the English is set in the same style, in the same box (same baseline, same left edge or centre).
Chromium does the typesetting (tools/retext_render.mjs), so kerning, letter-spacing and wrapping are real.
A badge (pill) behind a line is redrawn to fit the new text, and a glyph that follows a line (a chevron)
moves with its end. Verses are the KJV (public domain).

Usage: python3 tools/retext.py [--review DIR]  -> RISE_presentation/1_captures_clair_en/{15,17,18}_*.png
                                                 and .../extraits/{post_verset,answer_1}.png
With --review, DIR gets an original | French re-rendered | English strip per image (the middle one must
look like the first: that checks the font, the size and the position).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.sparse import diags, identity, kron
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent.parent / "RISE_presentation"
CAP = SRC / "1_captures_clair"
OUT = SRC / "1_captures_clair_en"
UI = ROOT / "assets" / "ui"  # the pieces cut from the clips' frames (prepare_assets.py)
FS = ROOT / "node_modules" / "@fontsource"
FONTS = ([{"family": "Inter", "weight": w, "style": "normal", "file": str(FS / f"inter/files/inter-latin-{w}-normal.woff2")}
          for w in range(100, 1000, 100)] +
         [{"family": "Newsreader", "weight": w, "style": s, "file": str(FS / f"newsreader/files/newsreader-latin-{w}-{s}.woff2")}
          for w in range(200, 900, 100) for s in ("normal", "italic")])

# ---------- what is replaced: the French line's box (only that line in it), the two texts, the style ----------
# sizes are first guesses (the fit sets them); lh is the line height in px, width the wrapping width
Q = dict(font="Inter", weight=700, size=54, lh=80, width=976)
ANS = dict(font="Inter", weight=600, size=37)
QUESTION = [
    dict(box=(40, 318, 420, 372), fr="QUESTION 1 SUR 5", en="QUESTION 1 OF 5", font="Inter", weight=700, size=27, ls=0.12),
    dict(box=(40, 390, 1040, 552), fr="De quoi l’Éternel Dieu forma-t-il\nl’homme ?", en="What did the LORD God use to form man?", **Q),
    dict(box=(80, 662, 900, 735), fr="De la poussière de la terre", en="The dust of the ground", **ANS),
    dict(box=(80, 835, 900, 905), fr="De l’argile d’un fleuve", en="Clay from a river", **ANS),
    dict(box=(80, 1005, 900, 1085), fr="D’une côte", en="A rib", **ANS),
    dict(box=(80, 1180, 900, 1255), fr="D’un rocher", en="A rock", **ANS),
]
DAYS = [(127, "L", "M"), (265, "M", "T"), (402, "M", "W"), (540, "J", "T"), (677, "V", "F"), (952, "D", "S")]  # S stays S
SPECS = {
    "15_quiz_parcours": (CAP / "15_quiz_parcours.png", OUT / "15_quiz_parcours.png", [
        dict(box=(160, 160, 700, 278), fr="Quiz biblique", en="Bible Quiz", font="Newsreader", weight=600, size=80),
        # the stats card (the hook's quiz card)
        dict(box=(80, 418, 330, 474), fr="jours d’affilée", en="day streak", font="Inter", weight=400, size=32),
        dict(box=(680, 418, 900, 474), fr="niveaux", en="levels", font="Inter", weight=400, size=32),
        *[dict(box=(x - 34, 510, x + 34, 560), fr=fr, en=en, font="Inter", weight=700 if fr == "J" else 500, size=31,
               align="center", cw=200, fit="h") for x, fr, en in DAYS],
        dict(box=(80, 685, 330, 742), fr="Semeur", en="Sower", font="Inter", weight=700, size=37),
        dict(box=(80, 782, 760, 840), fr="Encore 120 pts pour devenir « Berger »", en="120 more pts to become “Shepherd”",
             font="Inter", weight=400, size=32),
        # the unit card
        dict(box=(84, 1160, 330, 1209), fr="UNITÉ 2", en="UNIT 2", font="Inter", weight=700, size=28, ls=0.12),
        dict(box=(80, 1212, 720, 1278), fr="La création et les débuts", en="Creation and beginnings", font="Inter", weight=700, size=44),
        # the path, on the sky
        dict(box=(430, 1628, 650, 1680), fr="La création", en="Creation", font="Inter", weight=500, size=34, align="center", cw=600),
        dict(box=(272, 1703, 555, 1767), measure=(293, 1714, 534, 1755), pill=(279, 1708, 548, 1761),
             fr="AUJOURD’HUI", en="TODAY", font="Inter", weight=700, size=28, ls=0.12, align="center", cw=600),
        dict(box=(225, 1996, 605, 2055), fr="Adam et Ève au jardin", en="Adam and Eve in the garden", font="Inter", weight=700,
             size=34, align="center", cw=800),
        dict(box=(236, 2316, 398, 2361), fr="La chute", en="The Fall", font="Inter", weight=500, size=34, align="center", cw=600),
    ]),
    "17_quiz_question": (CAP / "17_quiz_question.png", OUT / "17_quiz_question.png", QUESTION + [
        dict(box=(300, 2200, 780, 2280), fr="Valider", en="Check", font="Inter", weight=600, size=37, align="center"),
    ]),
    # the same question, the first answer now green, and the "Exact !" sheet
    "18_quiz_reponse": (CAP / "18_quiz_reponse.png", OUT / "18_quiz_reponse.png", QUESTION + [
        dict(box=(130, 1745, 700, 1825), fr="Exact !", en="Correct!", font="Inter", weight=700, size=50),
        dict(box=(40, 1868, 1040, 2050),
             fr="Formé de la poussière, l’homme ne devint un être\nvivant que lorsque Dieu souffla dans ses narines un\nsouffle de vie.",
             en="Formed from the dust, man became a living soul only when God breathed into his nostrils the breath of life.",
             font="Inter", weight=400, size=37, lh=58, width=976),
        dict(box=(100, 2068, 430, 2120), fr="Genèse 2:7 · LSG", en="Genesis 2:7 · KJV", font="Inter", weight=600, size=32,
             follow=(403, 2080, 422, 2110)),
        dict(box=(300, 2200, 780, 2280), fr="Continuer", en="Continue", font="Inter", weight=600, size=37, align="center"),
    ]),
    # David's post in the feed clip (a video frame): his verse of the week
    "post_verset": (UI / "post_verset.png", OUT / "extraits" / "post_verset.png", [
        dict(box=(120, 88, 800, 146), fr="Le verset qui me porte cette semaine.", en="The verse carrying me this week.",
             font="Inter", weight=400, size=39),
        dict(box=(185, 188, 470, 234), fr="Ésaïe 40:31 — LSG", en="Isaiah 40:31 — KJV", font="Inter", weight=600, size=26,
             color="rgb(217,119,6)"),  # the app's amber, as on the unit card (the video frame dulls it)
        dict(box=(185, 240, 1000, 490),
             fr="« Mais ceux qui se confient en l’Éternel\nrenouvellent leur force. Ils prennent le vol comme\n"
                "les aigles ; ils courent, et ne se lassent point, ils\nmarchent, et ne se fatiguent point. »",
             en="“But they that wait upon the LORD shall renew their strength; they shall mount up with wings as eagles; "
                "they shall run, and not be weary; and they shall walk, and not faint.”",
             font="Newsreader", weight=400, size=36, italic=True, lh=60, width=790),
    ]),
    # the first answer of the quiz clip, not yet chosen
    "answer_1": (UI / "answer_1.png", OUT / "extraits" / "answer_1.png", [
        dict(box=(30, 40, 850, 112), fr="De la poussière de la terre", en="The dust of the ground", **ANS),
    ]),
}


def harmonic_fill(a, box):
    """a: float HxWx3. The inside of box (x0, y0, x1, y1) solved from Laplace's equation, the pixels just
    outside the box being the boundary values."""
    x0, y0, x1, y1 = box
    h, w = y1 - y0, x1 - x0
    T = lambda n: diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1])
    A = (kron(identity(h), T(w)) + kron(T(h), identity(w))).tocsc()
    B = np.zeros((h, w, 3))
    B[0] += a[y0 - 1, x0:x1]
    B[-1] += a[y1, x0:x1]
    B[:, 0] += a[y0:y1, x0 - 1]
    B[:, -1] += a[y0:y1, x1]
    out = a.copy()
    out[y0:y1, x0:x1] = splu(A).solve(B.reshape(-1, 3)).reshape(h, w, 3)
    return out


def ink(a, bg, box, frac=0.3):
    """The text in box against its background: (bbox of coverage > frac, text colour, coverage map)."""
    x0, y0, x1, y1 = box
    d = np.abs(a[y0:y1, x0:x1] - bg[y0:y1, x0:x1]).sum(axis=2)
    cov = d / (d.max() or 1)
    ys, xs = np.where(cov > frac)
    color = np.median(a[y0:y1, x0:x1][cov > 0.85], axis=0)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1), color, cov


def render(jobs):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    subprocess.run(["node", str(ROOT / "tools" / "retext_render.mjs"), f.name], check=True)
    Path(f.name).unlink()


def css(it, left, top):
    s = (f"left:{left:.2f}px;top:{top:.2f}px;font-family:{it['font']};font-weight:{it['weight']};font-size:{it['size']:.3f}px;"
         f"color:{it['rgb']};letter-spacing:{it.get('ls', 0)}em;font-style:{'italic' if it.get('italic') else 'normal'};"
         f"line-height:{it.get('lh', it['size'] * 1.3):.3f}px;")
    if it.get("width"):
        s += f"width:{it['width']}px;"
    if it.get("align") == "center":
        s += f"width:{it['cw']}px;text-align:center;"
    return s


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def alone(it, text, work, L0=40.0, T0=40.0):
    """Ink bbox of `text` set alone at (L0, T0) with the item's style, and its alpha."""
    W = int(max(it["ink"][2] - it["ink"][0], it.get("width") or 0, it.get("cw", 0), 1000) + 2 * L0 + 200)
    H = int((it["ink"][3] - it["ink"][1]) + 2 * T0 + it["size"] * 4)
    out = str(work / "alone.png")
    render([{"out": out, "width": W, "height": H, "background": None, "fonts": FONTS,
             "items": [{"html": esc(text), "style": css(it, L0, T0)}]}])
    al = np.asarray(Image.open(out))[:, :, 3] / 255.0
    ys, xs = np.where(al > 0.3)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), al


def line_tops(mask):
    rows = np.where(mask.any(axis=1))[0]
    return [rows[0]] + [b for a, b in zip(rows[:-1], rows[1:]) if b - a > 6]


def calibrate(it, cov, work, L0=40.0, T0=40.0):
    """Fit the size (then the line height) so the re-rendered French covers the original's ink; place the box."""
    ox0, oy0, ox1, oy1 = it["ink"]
    for _ in range(5):
        (rx0, ry0, rx1, ry1), al = alone(it, it["fr"], work, L0, T0)
        it["ratio_w"], it["ratio_h"] = (ox1 - ox0) / (rx1 - rx0), (oy1 - oy0) / (ry1 - ry0)
        ratio = it["ratio_h"] if it.get("fit") == "h" else it["ratio_w"]
        if abs(ratio - 1) < 0.002:
            break
        it["size"] *= ratio
    if "\n" in it["fr"]:
        for _ in range(3):
            o, r = line_tops(cov > 0.3), line_tops(al > 0.3)
            n = min(len(o), len(r))
            err = ((o[n - 1] - o[0]) - (r[n - 1] - r[0])) / (n - 1)
            if abs(err) < 0.3:
                break
            it["lh"] += err
            (rx0, ry0, rx1, ry1), al = alone(it, it["fr"], work, L0, T0)
    it["left"] = L0 + (((ox0 + ox1) - (rx0 + rx1)) / 2 if it.get("align") == "center" else ox0 - rx0)
    it["top"] = T0 + (oy0 - ry0)


def retext(name, review=None):
    src_path, out_path, spec = SPECS[name]
    src = Image.open(src_path).convert("RGB")
    a = np.asarray(src).astype(float)
    bg = a.copy()
    items = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for it in spec:
            it = dict(it)
            box = it["box"]
            filled = harmonic_fill(a, box)
            if it.get("follow"):
                mbox, mbg = (box[0], box[1], it["follow"][0] - 2, box[3]), filled
            elif it.get("measure"):
                mbox = it["measure"]
                mbg = harmonic_fill(a, mbox)
            else:
                mbox, mbg = box, filled
            it["ink"], color, cov = ink(a, mbg, mbox)
            it["rgb"] = it.get("color") or "rgb({},{},{})".format(*np.round(color).astype(int))
            it.setdefault("cw", box[2] - box[0])
            bg[box[1]:box[3], box[0]:box[2]] = filled[box[1]:box[3], box[0]:box[2]]
            calibrate(it, cov, work)
            if it.get("pill"):
                # the badge behind the line: redrawn around the new text, same padding, same colour
                px0, py0, px1, py1 = it["pill"]
                rgb = "rgb({},{},{})".format(*np.round(np.median(a[mbox[1]:mbox[3], mbox[0]:mbox[2]][cov < 0.03], axis=0)).astype(int))
                (ex0, _, ex1, _), _ = alone(it, it["en"], work)
                ex0, ex1 = it["left"] + ex0 - 40, it["left"] + ex1 - 40
                pill = lambda x0, x1: (f'<div style="position:absolute;left:{x0:.2f}px;top:{py0}px;width:{x1 - x0:.2f}px;'
                                       f'height:{py1 - py0}px;border-radius:{(py1 - py0) / 2}px;background:{rgb}"></div>')
                it["under_fr"] = pill(px0, px1)
                it["under_en"] = pill(ex0 - (it["ink"][0] - px0), ex1 + (px1 - it["ink"][2]))
            print(f"  {it['en'][:36]!r:40s} {it['font']} {it['weight']} {it['size']:.1f}px  fit w×{it['ratio_w']:.3f} h×{it['ratio_h']:.3f}")
            items.append(it)
        Image.fromarray(np.clip(bg, 0, 255).round().astype(np.uint8)).save(work / "bg.png")
        h, w = a.shape[:2]
        jobs = [{"out": str(work / f"{lang}.png"), "width": w, "height": h, "background": str(work / "bg.png"), "fonts": FONTS,
                 "items": [{"html": it[f"under_{lang}"], "style": ""} for it in items if it.get(f"under_{lang}")] +
                          [{"html": esc(it[lang]), "style": css(it, it["left"], it["top"])} for it in items]}
                for lang in ("fr", "en")]
        render(jobs)
        fr = np.asarray(Image.open(work / "fr.png").convert("RGB")).astype(float)
        en = np.asarray(Image.open(work / "en.png").convert("RGB")).astype(float)
    # a glyph that follows a line (the chevron after a link) keeps its gap to the line's new end
    for it in items:
        if it.get("follow"):
            gx0, gy0, gx1, gy1 = it["follow"]
            x0, y0, x1, y1 = it["box"]
            right = lambda img, x1: x0 + np.where((ink(img, bg, (x0, y0, x1, y1))[2] > 0.3).any(axis=0))[0].max() + 1
            nx = gx0 + right(en, x1) - right(a, gx0 - 2)
            en[gy0:gy1, nx:nx + gx1 - gx0] = a[gy0:gy1, gx0:gx1]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(en, 0, 255).round().astype(np.uint8)).save(out_path)
    worst = max(np.abs(fr - a)[it["box"][1]:it["box"][3], it["box"][0]:it["box"][2]].mean() for it in items if not it.get("follow"))
    print(f"{name}: {len(items)} lines -> {out_path.relative_to(SRC.parent)}  (French re-rendered vs original: worst mean diff {worst:.1f})")
    if review:
        strip = Image.new("RGB", (w * 3 + 40, h), "white")
        for i, im in enumerate((a, fr, en)):
            strip.paste(Image.fromarray(np.clip(im, 0, 255).round().astype(np.uint8)), (i * (w + 20), 0))
        strip.save(Path(review) / f"review_{name}.png")


if __name__ == "__main__":
    review = sys.argv[sys.argv.index("--review") + 1] if "--review" in sys.argv else None
    for name in SPECS:
        retext(name, review)
