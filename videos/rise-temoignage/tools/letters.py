"""Words written as drawings: the Hershey single-stroke letters (assets/hershey.json), French accents drawn on
top, laid out in any coordinates, written stroke by stroke (with where the pen's tip is, to draw the hand that
holds it).
"""
import json
import math
import random
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERSHEY = json.loads((ROOT / "assets" / "hershey.json").read_text())
CAP, BASE = -12.0, 9.0  # the fonts' cap line and baseline, in their units
UNIT = BASE - CAP  # 21 units = the cap height


def _glyph(font, ch):
    g = HERSHEY[font].get(ch)
    return g if g is not None else HERSHEY[font]["?"]


def _bounds(strokes):
    xs = [x for s in strokes for x, _ in s]
    ys = [y for s in strokes for _, y in s]
    return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, 0, 0, 0)


def _mark(mark, x0, x1, top, upper):
    """A French accent, in font units, over (or under) a letter spanning x0..x1 whose top is `top`."""
    cx = (x0 + x1) / 2 + (1.5 if not upper else 0)
    y = (top - 3.5) if not upper else (CAP - 4)
    if mark == "́":  # acute
        return [[(cx - 1.2, y + 1.2), (cx + 2.4, y - 2.6)]]
    if mark == "̀":  # grave
        return [[(cx - 2.2, y - 2.6), (cx + 1.2, y + 1.2)]]
    if mark == "̂":  # circumflex
        return [[(cx - 2.6, y + 0.8), (cx, y - 2.4), (cx + 2.6, y + 0.8)]]
    if mark == "̈":  # diaeresis
        return [[(cx - 2.0, y), (cx - 1.6, y + 0.4)], [(cx + 2.0, y), (cx + 2.4, y + 0.4)]]
    if mark == "̧":  # cedilla
        return [[(cx, BASE), (cx + 1.4, BASE + 2.2), (cx - 0.4, BASE + 4.2), (cx - 2.2, BASE + 3.6)]]
    return []


def layout(text, font="futural", size=40.0, slant=0.0, hand=0.0, seed=0):
    """The text's strokes in its own units scaled to `size` px of cap height: x from 0, baseline at y=0.
    hand > 0 makes it look written by hand: every letter a little turned, sized and lifted its own way.
    Returns (strokes, width)."""
    k = size / UNIT
    rng = random.Random(seed)
    pen_x, out = 0.0, []
    for ch in text:
        parts = unicodedata.normalize("NFD", ch)
        base, marks = parts[0], parts[1:]
        if base == "i" and marks:  # î, ï: the accent takes the dot's place
            base = "ı" if "ı" in HERSHEY[font] else "i"
        g = _glyph(font, base)
        strokes = [[(x + pen_x, y) for x, y in s] for s in g["s"]]
        if base == "i" and marks and len(strokes) > 1:
            strokes = [max(strokes, key=lambda s: _bounds([s])[3] - _bounds([s])[2])]
        if strokes and marks:
            x0, x1, top, _ = _bounds(strokes)
            for m in marks:
                strokes += [[(x, y) for x, y in s] for s in _mark(m, x0, x1, top, base.isupper())]
        if hand and strokes:
            x0, x1, _, _ = _bounds(strokes)
            cx = (x0 + x1) / 2
            a = math.radians(rng.gauss(0, 2.2 * hand))
            sc = 1 + rng.gauss(0, 0.035 * hand)
            dy = rng.gauss(0, 0.45 * hand)
            ca, sa = math.cos(a), math.sin(a)
            strokes = [[(cx + ((x - cx) * ca - (y - BASE) * sa) * sc, BASE + ((x - cx) * sa + (y - BASE) * ca) * sc + dy) for x, y in s]
                       for s in strokes]
        for s in strokes:
            out.append([((x + slant * (BASE - y)) * k, (y - BASE) * k) for x, y in s])
        pen_x += g["a"] * (1 + (rng.gauss(0, 0.03 * hand) if hand else 0))
    return out, pen_x * k


def place(strokes, fn):
    """The strokes moved by fn(x, y) -> (x, y) (onto a page, a card in perspective, ...)."""
    return [[fn(x, y) for x, y in s] for s in strokes]


def length(stroke):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))


def written(strokes, p):
    """The strokes as far as a pen has gone through them at progress p (0..1, by length), and where its tip is."""
    total = sum(length(s) for s in strokes) or 1.0
    goal, done, out, tip = total * max(0.0, min(1.0, p)), 0.0, [], None
    for s in strokes:
        L = length(s)
        if done + L <= goal:
            out.append(s)
            done += L
            tip = s[-1]
            continue
        part, left = [s[0]], goal - done
        for a, b in zip(s, s[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            if d <= left:
                part.append(b)
                left -= d
            else:
                f = left / d if d else 0
                pt = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                part.append(pt)
                tip = pt
                break
        if len(part) > 1:
            out.append(part)
        break
    return out, tip


def width(text, font="futural", size=40.0):
    return layout(text, font, size)[1]


def wrap(text, font, size, max_w):
    """Lines of words that fit max_w."""
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if cur and width(t, font, size) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines
