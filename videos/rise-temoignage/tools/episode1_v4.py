"""Tony's testimony, episode 1, v4: something new draws itself on every phrase.

v3 held one picture too long. Here every phrase brings its own drawing, and every drawing draws itself: each
stroke is traced from its start, as if a hand were drawing it live (the pen's progress, patched into
draw_test's Pen). Pictures build up phrase after phrase; shots cross over with a push of the camera; the
report card is reached by diving into the paper on the schoolboy's desk. Words hand-lettered (v3).
Usage: python3 tools/episode1_v4.py [t ...]  -> renders/episode1_v4.mp4, or stills at the given times
"""
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageChops, ImageDraw, ImageFont

import draw_test as dt
import episode1 as ep
import episode1_v3 as v3
from draw_test import Pen, arc, bez

ROOT = v3.ROOT
W, H, S, FPS = 1080, 1920, dt.S, 24
HAND = ImageFont.truetype(str(ROOT / "assets/fonts/patrick-hand-latin-400-normal.woff"), 46 * S)

# --- the pen draws its strokes from their start: PROG is how far along each stroke is
PROG = [1.0]
_line, _poly, _bubble = dt.Pen.line, dt.Pen.poly, dt.bubble


def partial(pts, p):
    pts = np.asarray(pts, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.cumsum(seg)
    target = cum[-1] * p
    i = int(np.searchsorted(cum, target))
    if i >= len(seg):
        return pts.tolist()
    frac = (target - (cum[i] - seg[i])) / max(seg[i], 1e-6)
    return pts[: i + 1].tolist() + [(pts[i] + (pts[i + 1] - pts[i]) * frac).tolist()]


def line_on(self, pts, w=4, amp=1.6, fill=255):
    if PROG[0] < 1:
        if PROG[0] <= 0 or len(pts) < 2:
            return
        pts = partial(pts, PROG[0])
    _line(self, pts, w, amp, fill)


def poly_on(self, pts, fill=255):
    if PROG[0] >= 0.97:
        _poly(self, pts, fill)


SHOW_BUBBLES = [True]
dt.Pen.line, dt.Pen.poly = line_on, poly_on
dt.bubble = lambda *a, **k: _bubble(*a, **k) if SHOW_BUBBLES[0] else None

# --- the timeline: v3's words, with room to read the report card and to see RISE light up
EXTRA = {"…parfois même par des proches.": 2.0, "Alors j'ai créé RISE.": 0.4}
LINES, t = [], 0.0
for text, scene in v3.SCRIPT:
    d = max(1.3, len(text.split()) / v3.WPS) + v3.PAUSE + EXTRA.get(text, 0)
    LINES.append(dict(text=text, t0=t, t1=t + d))
    t += d
LINES[-1]["t1"] += v3.END_HOLD
DURATION = LINES[-1]["t1"]
L = [l["t0"] for l in LINES]  # when each phrase starts
SHOTS = [("phone1", 0, 1), ("tony", 2, 6), ("school", 7, 9), ("card", 9, 9), ("shell", 10, 17), ("crowd", 18, 19),
         ("rise", 20, 25), ("gather", 26, 27), ("logo", 28, 28)]
DIVE = L[9] + 0.8  # into the report card on the desk
CARD_END = L[10]


def shot_span(name):
    _, a, b = next(s for s in SHOTS if s[0] == name)
    t0 = DIVE if name == "card" else L[a]
    t1 = DIVE if name == "school" else (CARD_END if name == "card" else LINES[b]["t1"])
    return t0, t1


def ease(x):
    return v3.ease(x)


def prog(t, at, dur=0.7):
    return min(1.0, max(0.0, (t - at) / dur))


def layer(cache, key, variant, p, fn, still=True):
    """One drawn element at draw-on progress p; kept once fully drawn."""
    k = (key, variant)
    if still and p >= 1 and k in cache:
        return cache[k]
    img = Image.new("L", (W * S, H * S), 0)
    pen = Pen(img, np.random.default_rng(abs(hash(key)) % 10 ** 6 * 10 + variant))
    PROG[0] = p
    fn(pen)
    PROG[0] = 1.0
    out = img.resize((W, H), Image.LANCZOS)
    if still and p >= 1:
        cache[k] = out
    return out


def over(base, *layers):
    for la in layers:
        base = ImageChops.lighter(base, la)
    return base


# --- small drawings
def person(pen, x, y, s=1.0, glasses=False, w=3.2):
    r = 38 * s
    pen.line(arc(x, y - 92 * s, r, r * 1.08, 0, 360, 36), w=w)
    pen.line(bez((x - 78 * s, y + 46 * s), (x - 62 * s, y - 42 * s), (x + 62 * s, y - 42 * s), (x + 78 * s, y + 46 * s)), w=w)
    if glasses:
        for gx in (x - 15 * s, x + 15 * s):
            pen.line(arc(gx, y - 94 * s, 11 * s, 10 * s, 0, 360, 20), w=1.8)


def flame(pen, x, y, s=1.0, w=5):
    pen.line(bez((x, y - 70 * s), (x + 58 * s, y - 8 * s), (x + 44 * s, y + 48 * s), (x, y + 48 * s))
             + bez((x, y + 48 * s), (x - 44 * s, y + 48 * s), (x - 58 * s, y - 8 * s), (x, y - 70 * s))[1:], w=w)


def phone_body(pen, x, y, w, h, lw=5):
    body = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
    pen.line(body + body[:1], w=lw)
    pen.line([(x - 40, y - h / 2 + 24), (x + 40, y - h / 2 + 24)], w=lw - 1)


def chat(pen, cx, cy, w, h, side=1, lines=2, lw=3.2):
    pen.line(arc(cx, cy, w / 2, h / 2, 0, 360, 50), w=lw)
    tx = cx + side * w * 0.3
    pen.line([(tx - 16, cy + h * 0.45), (tx + side * 28, cy + h * 0.5 + 30), (tx + 16, cy + h * 0.45)], w=lw - 0.4)
    for i in range(lines):
        ly = cy - h * 0.2 + i * h * 0.24
        pen.line([(cx - w * 0.3 + j * w * 0.05, ly + 4 * math.sin(j * 1.7 + cx)) for j in range(12 if i < lines - 1 else 7)], w=2.2, amp=1.0)


def glow(pen, x, y, r0, r1, n=60, sy=1.0):
    for a in np.linspace(0, 360, n, endpoint=False):
        ra = math.radians(a + pen.rng.uniform(-3, 3))
        rr = r0 + (r1 - r0) * pen.rng.uniform(0.5, 1)
        pen.line([(x + r0 * math.cos(ra), y + r0 * sy * math.sin(ra)), (x + rr * math.cos(ra), y + rr * sy * math.sin(ra))], w=1.3, amp=0.3)


def scribble_out(pen, x, y, w, h):
    """Crossed out, quickly: two strokes."""
    pen.line([(x - w / 2, y - h / 2), (x + w / 2, y + h / 2)], w=6)
    pen.line([(x + w / 2, y - h / 2), (x - w / 2, y + h / 2)], w=6)


# --- the shots: each returns the picture (L) at t
def shot_phone1(f, t, v, c):
    els = [layer(c, "p1", v, prog(t, L[0], 0.8), lambda p: phone_body(p, 540, 1180, 380, 720)),
           layer(c, "p1f", v, prog(t, L[0] + 0.6, 0.5), lambda p: flame(p, 540, 1150, 1.2))]
    if t > L[0] + 0.9:
        els.append(layer(c, "p1g", v, 1, lambda p: glow(p, 540, 1180, 400, 470, 80, 1.8), still=True))
    for k, (x, y, w, h, side) in enumerate([(200, 560, 300, 130, -1), (860, 520, 290, 120, 1), (180, 860, 280, 115, -1),
                                            (880, 820, 270, 125, 1), (200, 1500, 270, 110, -1), (880, 1480, 280, 115, 1)]):
        at = L[1] + 0.15 * k
        if t > at:
            s = 0.6 + 0.4 * ease((t - at) / 0.22)
            els.append(layer(c, f"c{k}", v, 1 if s >= 1 else 0.99, lambda p, x=x, y=y, w=w, h=h, side=side, s=s: chat(p, x, y, w * s, h * s, side), still=s >= 1))
    if t > L[1] + 1.1:  # his own: three dots, no words
        def mine(p):
            chat(p, 790, 1730, 220, 110, -1, lines=0)
            for i in range(3):
                r = 9 + 3 * max(0, math.sin(t * 6 - i))
                p.d.ellipse([(754 + 36 * i - r) * S, (1730 - r) * S, (754 + 36 * i + r) * S, (1730 + r) * S], fill=255)
        els.append(layer(c, "mine", v, 1, mine, still=False))
    return over(Image.new("L", (W, H), 0), *els)


def tony(c, v, p):
    k = ("tony", v)
    if p >= 1 and k in c:
        return c[k]
    SHOW_BUBBLES[0] = False
    PROG[0] = p
    img = dt.draw(v, 0.0)
    PROG[0] = 1.0
    SHOW_BUBBLES[0] = True
    if p >= 1:
        c[k] = img
    return img


def shot_tony(f, t, v, c):
    els = [tony(c, v, prog(t, L[2], 1.4))]
    if t > L[3]:  # others, together, further off
        def group(p):
            for i, (x, y) in enumerate(((760, 470), (880, 440), (990, 490))):
                person(p, x, y, 0.75)
            chat(p, 820, 300, 150, 70, 1, 1, 2.6)
            chat(p, 960, 280, 130, 64, -1, 1, 2.6)
        els.append(layer(c, "group", v, prog(t, L[3], 0.9), group))
    if L[4] < t < L[6] + 0.3:  # a question he won't ask
        els.append(layer(c, "q", v, prog(t, L[4], 0.5), lambda p: p.line(arc(300, 640, 50, 50, 200, 400, 30) + [(300, 720)], w=7)))
        if t > L[4] + 1.0:
            els.append(layer(c, "qx", v, prog(t, L[4] + 1.0, 0.35), lambda p: scribble_out(p, 300, 680, 150, 170)))
    if L[5] < t < L[6] + 0.3:  # words that don't come out
        els.append(layer(c, "say", v, prog(t, L[5], 0.5), lambda p: chat(p, 260, 1000, 300, 150, 1, 3)))
        if t > L[5] + 1.1:
            els.append(layer(c, "sayx", v, prog(t, L[5] + 1.1, 0.3), lambda p: (p.line([(130, 900), (390, 1100)], w=6), p.line([(390, 900), (130, 1100)], w=6))))
    if t > L[6]:  # his bubble shrinks back to nothing
        s = 1 - ease((t - L[6] - 0.3) / 1.2)
        if s > 0.05:
            els.append(layer(c, "back", v, 1, lambda p: chat(p, 480 + 60 * (1 - s), 1130, 180 * s, 90 * s, 1, 0), still=False))
    return over(Image.new("L", (W, H), 0), *els)


def kid_desk(p):
    person(p, 540, 1240, 1.6, glasses=True, w=4)
    for k in range(14):  # his hair
        a = math.radians(200 + k * 10)
        p.line([(540 + 60 * math.cos(a), 1092 + 64 * math.sin(a)), (540 + 64 * math.cos(a) + 6, 1092 + 68 * math.sin(a) - 22)], w=2)
    p.line([(200, 1330), (880, 1330)], w=5)
    p.line([(230, 1330), (230, 1600)], w=4)
    p.line([(850, 1330), (850, 1600)], w=4)
    p.line([(470, 1345), (650, 1340), (660, 1400), (462, 1405), (470, 1345)], w=3)  # the report card on the desk


def shot_school(f, t, v, c):
    els = [layer(c, "kid", v, prog(t, L[7], 1.1), kid_desk)]
    if t > L[8]:  # friends who laugh
        def friends(p):
            person(p, 170, 1080, 1.0)
            person(p, 320, 1040, 1.0)
            p.d.text((110 * S, 870 * S), "ha ha", font=HAND, fill=255)
        els.append(layer(c, "friends", v, prog(t, L[8], 0.6), friends))
    if t > L[8] + 0.9:  # a teacher who points
        def teacher(p):
            person(p, 900, 1010, 1.3, glasses=True)
            p.line([(840, 980), (720, 920), (690, 915)], w=4)
        els.append(layer(c, "teacher", v, prog(t, L[8] + 0.9, 0.6), teacher))
    if t > L[9]:  # and those close to him, behind
        def close(p):
            person(p, 380, 760, 1.5)
            person(p, 700, 740, 1.5)
        els.append(layer(c, "close", v, prog(t, L[9], 0.6), close))
    return over(Image.new("L", (W, H), 0), *els)


def shot_card(f, t, v, c):
    ep.WRITE0, ep.WRITE1 = DIVE + 0.4, DIVE + 1.9
    if f"card{v}" not in c:
        c[f"card{v}"] = ep.report_card(v)
    base = Image.new("RGB", (W, H), 0)
    base.paste(c[f"card{v}"].convert("RGB"), (0, 0))
    ink = ep.ink_at(t)
    if ink is not None:
        base.paste(ink, (0, 0), ink)
    return base


SH_C, SH_S = (590, 1300), 0.72  # the camera pulls back on him: everything about this point, to this scale
DOME = (590, 1300 + (1180 - 1300) * SH_S, 500 * SH_S, 700 * SH_S)  # the shell, once he is small: cx, cy, rx, ry


def shot_shell(f, t, v, c):
    s = 1 - (1 - SH_S) * ease((t - L[10]) / 1.2)
    me = tony(c, v, 1)
    dim = 1 - 0.4 * ease((t - L[15]) / 1.0)
    if dim < 1:
        me = Image.eval(me, lambda x: int(x * dim))
    ep.S4 = L[12] - 0.25
    sh = ep.shell(v, ep.S4 + (t - ep.S4) * 2.0).resize((W, H), Image.LANCZOS) if t > L[12] - 0.25 else None
    pic = me if sh is None else Image.composite(sh, me, sh.point(lambda x: 255 if x > 0 else 0))
    pic = v3.cam(pic, s, *SH_C)
    els = []
    cx, cy, rx, ry = DOME
    head = (611, 1062)
    if L[11] < t < L[12] + 0.6:  # ideas flying back into his head
        def ideas(p):
            for k in range(5):
                u = ease((t - L[11] - 0.25 * k) / 1.3)
                if u <= 0 or u >= 1:
                    continue
                x0, y0 = 150 + k * 190, 560 + (k % 2) * 90
                x, y = x0 + (head[0] - x0) * u, y0 + (head[1] - y0) * u
                r = 34 * (1 - u) + 4
                p.line(arc(x, y, r, r, 0, 360, 24), w=3)
                p.line([(x, y + r), (x, y + r + 12 * (1 - u))], w=2.5)
        els.append(layer(c, "ideas", v, 1, ideas, still=False))
    if L[13] < t < L[15]:  # it protects him: things thrown at it bounce off
        def darts(p):
            for k, (ang, at) in enumerate(((200, 0), (330, 0.35), (250, 0.7), (300, 1.05))):
                u = (t - L[13] - at) / 0.45
                if u <= 0:
                    continue
                a = math.radians(ang)
                ex, ey = cx + (rx + 10) * math.cos(a), cy + (ry + 10) * math.sin(a)
                sx, sy = cx + (rx + 420) * math.cos(a), cy + (ry + 420) * math.sin(a)
                if u < 1:
                    x, y = sx + (ex - sx) * u, sy + (ey - sy) * u
                else:  # bounced, falling away
                    b = min(1.5, u - 1)
                    x, y = ex + 90 * b * math.cos(a), ey + 90 * b * math.sin(a) + 200 * b * b
                dx, dy = math.cos(a), math.sin(a)
                p.line([(x + dx * 70, y + dy * 70), (x, y)], w=4)
                p.line([(x + dx * 20 - dy * 14, y + dy * 20 + dx * 14), (x, y), (x + dx * 20 + dy * 14, y + dy * 20 - dx * 14)], w=4)
        els.append(layer(c, "darts", v, 1, darts, still=False))
    if t > L[14]:  # the others, outside
        def outside(p):
            person(p, 110, 1360, 0.9)
            person(p, 980, 1360, 0.9)
            chat(p, 150, 1150, 130, 64, 1, 1, 2.4)
            chat(p, 940, 1150, 130, 64, -1, 1, 2.4)
        els.append(layer(c, "outside", v, prog(t, L[14], 0.7), outside))
    if t > L[15]:  # faith, inside: a small cross, lit
        def faith(p):
            p.line([(cx, cy - ry + 120), (cx, cy - ry + 230)], w=5)
            p.line([(cx - 38, cy - ry + 155), (cx + 38, cy - ry + 155)], w=5)
            glow(p, cx, cy - ry + 170, 70, 110, 40)
        els.append(layer(c, "faith", v, prog(t, L[15], 0.7), faith))
    if t > L[16]:  # questions, things to share: knocking against the walls
        fade = 1 - 0.6 * ease((t - L[17]) / 1.5)

        def inside(p):
            for k in range(4):
                u = t * (0.9 + 0.2 * k) + k * 1.7
                x = cx + (rx - 110) * 0.8 * math.sin(u)
                y = cy - ry * 0.35 + 110 * math.sin(u * 1.3 + k)
                if k % 2 == 0:
                    p.line(arc(x, y - 18, 22, 22, 200, 400, 20) + [(x, y + 14)], w=4, fill=int(255 * fade))
                else:
                    chat(p, x, y, 80, 46, 1, 1, 2.4)
        if t > L[16] + 0.2:
            els.append(layer(c, "inside", v, 1, inside, still=False))
    return over(pic, *els)


CROWD9 = [(220, 640), (820, 600), (520, 900), (170, 1160), (880, 1120), (420, 1420), (700, 1430), (240, 1700), (900, 1700)]


def shot_crowd(f, t, v, c):
    els = []
    for k, (x, y) in enumerate(CROWD9):
        at = L[18] + 0.45 * k if k < 3 else L[19] + 0.22 * (k - 3)
        if t > at:
            els.append(layer(c, f"m{k}", v, prog(t, at, 0.45), lambda p, x=x, y=y: v3.mini_shell(p, x, y, 0.8)))
    return over(Image.new("L", (W, H), 0), *els)


FEATURES = [(170, 700, "?"), (910, 1000, "p"), (170, 1320, "g")]  # beside the phone, one a phrase


def shot_rise(f, t, v, c):
    els = [layer(c, "r1", v, prog(t, L[20], 0.7), lambda p: phone_body(p, 540, 1080, 400, 760)),
           layer(c, "r1f", v, prog(t, L[20] + 0.5, 0.5), lambda p: flame(p, 540, 880, 0.8))]
    if t > L[20] + 0.9:
        els.append(layer(c, "r1g", v, 1, lambda p: glow(p, 540, 1080, 430, 500, 90, 1.8)))
    if t > L[21]:  # a feed, in the phone
        def feed(p):
            for k in range(3):
                y = 1000 + k * 150
                p.line([(380, y), (700, y), (700, y + 115), (380, y + 115), (380, y)], w=2.6)
                p.line(arc(420, y + 35, 18, 18, 0, 360, 16), w=2)
                p.line([(455, y + 30), (660, y + 30)], w=2)
                p.line([(400, y + 75), (680, y + 75)], w=2)
        els.append(layer(c, "feed", v, prog(t, L[21], 0.8), feed))
    for k, (x, y, kind) in enumerate(FEATURES):  # what you can do there, one card a phrase
        at = L[22 + k]
        if t > at:
            def card(p, x=x, y=y, kind=kind):
                p.line([(x - 120, y - 150), (x + 120, y - 150), (x + 120, y + 150), (x - 120, y + 150), (x - 120, y - 150)], w=3.4)
                v3.icon(p, kind, x, y - 20) if kind != "g" else v3.icon(p, kind, x, y - 90)
            els.append(layer(c, f"f{k}", v, prog(t, at, 0.5), card))
    if t > L[25]:  # without speaking up: from his small shell, a message goes
        def sent(p):
            v3.mini_shell(p, 540, 1760, 0.6)
            u = ease((t - L[25] - 0.5) / 1.2)
            if u > 0:
                y = 1640 - (1640 - 1470) * u
                chat(p, 540, y, 120, 56, 1, 1, 2.4)
        els.append(layer(c, "sent", v, prog(t, L[25], 0.5), sent, still=False))
    return over(Image.new("L", (W, H), 0), *els)


def shot_gather(f, t, v, c):
    a, b = shot_span("gather")
    return v3.crowd(v, t, (t - a) / (b - a - 0.6)).resize((W, H), Image.LANCZOS)


def shot_logo(f, t, v, c):
    a, _ = shot_span("logo")
    base = Image.new("RGB", (W, H), 0)
    sp = v3.splash_frame(t - a)
    base.paste(sp, ((W - sp.width) // 2, 760 - sp.height // 2), sp)
    return base


FN = {n: globals()[f"shot_{n}"] for n, _, _ in SHOTS}


def picture(f, t, c):
    v = (f // 3) % 3
    names = [n for n, _, _ in SHOTS]
    for i in range(len(names) - 1):
        a, b = names[i], names[i + 1]
        tb = shot_span(a)[1]
        if (a, b) == ("school", "card") and tb - 0.9 <= t < tb + 0.3:  # the dive into the paper on the desk
            u = ease((t - (tb - 0.9)) / 1.2)
            A = v3.cam(FN[a](f, t, v, c).convert("RGB"), 1 + 5.5 * u ** 1.5, 560, 1372, to=(560 + (540 - 560) * u, 1372 + (1000 - 1372) * u))
            k = min(1, max(0, (u - 0.55) / 0.4))
            if k <= 0:
                return A
            return Image.blend(A, v3.cam(shot_card(f, t, v, c), 1.25 - 0.25 * k, 540, 1000), k)
        if abs(t - tb) < v3.X and (a, b) != ("school", "card"):
            k = (t - (tb - v3.X)) / (2 * v3.X)
            A = v3.cam(FN[a](f, t, v, c).convert("RGB"), 1 + 0.12 * k, 540, 960)
            B = v3.cam(FN[b](f, t, v, c).convert("RGB"), 1.12 - 0.12 * k, 540, 960)
            return Image.blend(A, B, ease(k))
    name = next((n for n in names if shot_span(n)[0] <= t < shot_span(n)[1]), "logo")
    a, b = shot_span(name)
    pic = FN[name](f, t, v, c).convert("RGB")
    return pic if name == "logo" else v3.cam(pic, 1 + 0.035 * min(1, (t - a) / max(0.1, b - a)), 540, 960)


def frame(f, c):
    t = f / FPS
    v = (f // 3) % 3
    line = next(l for l in LINES if l["t0"] <= t < l["t1"] or l is LINES[-1])
    base = picture(f, t, c).convert("RGBA")
    tl = v3.TEXTS[(line["text"], v)]
    last = line is LINES[-1]
    a = ease((t - line["t0"] - (0.9 if last else 0)) / (0.5 if last else 0.15))
    if a > 0:
        if a < 1:
            tl = tl.copy()
            tl.putalpha(tl.getchannel("A").point(lambda x: int(x * a)))
        base.alpha_composite(tl, (0, 1040 if last else 150))
    return base.convert("RGB")


def sound(path):
    sr = 48000
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-t", str(DURATION), "-i", str(ep.MUSIC), "-ac", "2", "-ar", str(sr), f"{d}/m.wav"], check=True)
        m, _ = sf.read(f"{d}/m.wav", always_2d=True)
    n = int(DURATION * sr)
    m = np.pad(m, ((0, max(0, n - len(m))), (0, 0)))[:n]
    tt = np.arange(n) / sr
    h0 = L[28]
    y = m * 0.0  # no music (Tony asked): only his voice to come, and the boom under the logo
    boom, _ = sf.read(v3.BOOM, always_2d=True)
    at = int((h0 + 0.467) * sr)
    k = min(len(boom), n - at)
    y[at:at + k] += 0.8 * boom[:k]
    y /= max(1.0, np.max(np.abs(y)) / 0.89)
    sf.write(path, y, sr)


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        c = {}
        for f in range(int(DURATION * FPS)):
            frame(f, c).save(f"{d}/{f:05d}.png")
        sound(f"{d}/a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{d}/%05d.png", "-i", f"{d}/a.wav",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(out / "episode1_v4.mp4")], check=True)
    print(out / "episode1_v4.mp4", f"{DURATION:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        c = {}
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS), c).save(ROOT / f"still_{s}.png")
    else:
        main()
