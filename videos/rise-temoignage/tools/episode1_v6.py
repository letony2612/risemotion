"""Tony's testimony, episode 1, v6: the opening, drawn like an engraving, posed and drawn again for every drawing.

Tony asked for the best that can be done, and for everything to be drawn, the words too:
- the characters are rigs (tools/rig.py): Tony's head turns in space, blinks, looks about, smiles; his arms
  bend; his phone turns over; their strokes follow their forms and are as wide as the light on them;
- every word is written in single strokes (tools/letters.py): the captions, word by word as he speaks, the
  report card, the teacher's red pen;
- one camera, never a cut nor a dissolve: from his phone's screen back to him, across to the others, back,
  into the lens of his glasses and the classroom he remembers, down into the report card on his desk;
- twelve drawings a second, each held two frames, each drawn again (the lines boil); no music.
Usage: python3 tools/episode1_v6.py [--until s] [t ...]  -> renders/episode1_v6_opening.mp4, or stills
"""
import math
import subprocess
import sys
import tempfile
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import draw_test as dt
import ink
import letters
import rig
from rig import Canvas, draw_phone, draw_shadow, draw_tony, tony_pose

ROOT = Path(__file__).resolve().parents[1]
W, H, S = 1080, 1920, dt.S
FPS, DRAWINGS = 24, 12

# --- the pen draws its strokes from their start: PROG is how far along each stroke is (draw-on, rub-out)
PROG = [1.0]
_line, _poly = dt.Pen.line, dt.Pen.poly


def partial(pts, p):
    pts = np.asarray(pts, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.cumsum(seg)
    if len(cum) == 0 or cum[-1] <= 0:
        return pts.tolist()
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


dt.Pen.line, dt.Pen.poly = line_on, poly_on


class drawing:
    """Within: strokes drawn to progress p."""

    def __init__(self, p):
        self.p = p

    def __enter__(self):
        self.old = PROG[0]
        PROG[0] = max(0.0, min(1.0, self.p))
        return self

    def __exit__(self, *a):
        PROG[0] = self.old


class cam:
    """The camera: zoom z, the world's point p seen at the screen's point q."""

    def __init__(self, z=1.0, p=(540.0, 960.0), q=(540.0, 960.0)):
        self.v = [z, p[0], p[1], q[0], q[1]]

    def __enter__(self):
        self.old = dt.CAM[:]
        dt.CAM[:] = self.v
        return self

    def __exit__(self, *a):
        dt.CAM[:] = self.old


# --- the words (until Tony records them), and when each phrase starts
SCRIPT = [
    "J'ai créé un réseau social…",
    "…alors que j'ose même pas parler aux gens.",
    "Moi c'est Tony.",
    "Et je suis le genre de personne qui ose pas aller vers les autres.",
    "Qui ose pas poser de questions.",
    "Peut-être par peur de dire n'importe quoi…",
    "…ou peut-être par peur de déranger.",
    "Depuis tout jeune, j'ai souvent été rabaissé.",
    "Par des amis, par des profs…",
    "…parfois même par des proches.",
    "Alors j'ai appris à me faire petit.",
]
WPS, PAUSE = 3.0, 0.3
EXTRA = {"…ou peut-être par peur de déranger.": 0.5, "Depuis tout jeune, j'ai souvent été rabaissé.": 0.5, "…parfois même par des proches.": 4.1}
LINES, _t = [], 0.0
for _text in SCRIPT:
    _d = max(1.3, len(_text.split()) / WPS) + PAUSE + EXTRA.get(_text, 0)
    LINES.append(dict(text=_text, t0=_t, t1=_t + _d))
    _t += _d
L = [x["t0"] for x in LINES]


# --- motion
def clip01(x):
    return min(1.0, max(0.0, x))


def seg(t, a, b):
    return clip01((t - a) / (b - a)) if b > a else float(t >= a)


def ease(x):
    x = clip01(x)
    return x * x * (3 - 2 * x)


def eout(x):
    x = clip01(x)
    return 1 - (1 - x) ** 3


def ein(x):
    x = clip01(x)
    return x * x * x


def back(x, k=1.9):
    """Ease out past the mark, and back (an overshoot)."""
    x = clip01(x) - 1
    return 1 + x * x * ((k + 1) * x + k)


def lerp(a, b, u):
    return a + (b - a) * u


def lerp2(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def kf(t, keys, fn=ease):
    """A value moving through keyframes [(time, value), ...]."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t < t1:
            u = fn((t - t0) / (t1 - t0))
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return keys[-1][1]


def bump(t, a, dur):
    """0 -> 1 -> 0 over dur from a."""
    x = (t - a) / dur
    return math.sin(math.pi * x) if 0 < x < 1 else 0.0


# --- the timeline's marks (from the phrases: his voice will move them)
T_PULL = (1.9, 3.3)  # the camera backs away from his phone's screen
T_TALK = L[1] + 1.15  # the others' words pop up around him
T_WAVE = L[2] + 0.15
T_WIDE = (L[3], L[3] + 1.2)
T_STEP, T_HESIT, T_BACK = L[3] + 1.6, L[3] + 2.5, L[3] + 3.3
T_FLIP = L[3] + 3.9
T_RAISE, T_DROP = L[4] + 0.35, L[4] + 1.55
T_SAY, T_CRUMPLE, T_FALL = L[5] + 0.2, L[5] + 1.35, L[5] + 1.8
T_TYPE, T_ERASE = L[6] + 0.3, L[6] + 1.55
T_LENS = (L[7] + 0.35, L[7] + 1.75)
T_MATES, T_TEACH, T_CLOSE = L[8], L[8] + 1.0, L[9]
T_DIVE = (L[9] + 1.35, L[9] + 2.35)
T_WRITE = (T_DIVE[1] + 0.25, T_DIVE[1] + 2.55)
END = L[10]  # the report card stays until the next phrase

BLINKS = [1.2, 3.75, 6.2, 8.2, 10.6, 12.9, 15.0, 17.2, L[7] + 0.15]


def blink_at(t):
    return max([bump(t, b, 0.25) for b in BLINKS] + [0.0])


# --- Tony, posed at time t
PHONE = dict(cx=430.0, cy=1440.0, w=210.0, h=420.0, angle=-5.0)
POCKET = (705.0, 1960.0)


def tony_at(t):
    P = tony_pose()
    P["breath"] = 0.5 + 0.5 * math.sin(2 * math.pi * t / 3.4)
    ex = dict(blink=blink_at(t))
    yaw = pitch = roll = 0.0
    gx = gy = 0.0
    smile, opn, brow, worry, shrug, lean, dx = 0.35, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    ph = dict(PHONE, turn=0.0, glow=0.6)
    arm_l = dict(wrist=POCKET, hand="pocket", elbow=(1, 0.3))
    lift = 0.0

    # the others talk all round him: his smile goes, his eyes go from one to the other, he shrinks a little
    u = seg(t, T_TALK, T_TALK + 0.5)
    smile -= 0.3 * u
    worry += 0.55 * u * (1 - seg(t, L[2] - 0.2, L[2] + 0.2))
    shrug += 0.45 * u * (1 - seg(t, L[2] - 0.3, L[2] + 0.2))
    gx += kf(t, [(T_TALK + 0.1, 0.0), (T_TALK + 0.3, -0.75), (T_TALK + 0.85, -0.75), (T_TALK + 1.05, 0.75), (T_TALK + 1.5, 0.75),
                 (L[2] - 0.05, 0.0)])
    yaw += kf(t, [(T_TALK + 0.1, 0.0), (T_TALK + 0.35, -7.0), (T_TALK + 0.9, -7.0), (T_TALK + 1.1, 7.0), (T_TALK + 1.5, 7.0), (L[2] - 0.05, 0.0)])

    # « Moi c'est Tony. »: he looks at us, a small wave, a shy smile
    w_in = back(seg(t, T_WAVE, T_WAVE + 0.35))
    w_out = ease(seg(t, L[3] - 0.25, L[3] + 0.15))
    k_w = w_in * (1 - w_out)
    if k_w > 0.01:
        wave = math.sin((t - T_WAVE) * 2 * math.pi * 2.2) * seg(t, T_WAVE + 0.25, T_WAVE + 0.4) * (1 - seg(t, L[3] - 0.45, L[3] - 0.25))
        wr = lerp2(POCKET, (860.0 + 14 * wave, 1185.0), k_w)
        arm_l = dict(wrist=wr, hand="open" if k_w > 0.45 else "pocket", ang=-84 + 13 * wave, spread=0.9, elbow=(0.25, 1.0))
    sm = seg(t, L[2] - 0.1, L[2] + 0.3) * (1 - seg(t, L[3] + 0.4, L[3] + 0.9))
    smile += 0.35 * sm
    brow += 0.35 * sm
    roll += -4 * sm
    # « …qui ose pas aller vers les autres »: the camera finds the others; he looks, he goes, he stops, he goes back
    look = seg(t, T_WIDE[0] + 0.7, T_WIDE[0] + 1.0) * (1 - seg(t, T_BACK + 0.1, T_BACK + 0.5))
    yaw += 20 * look
    gx += 0.8 * look
    go = back(seg(t, T_STEP, T_STEP + 0.45), 1.2) * (1 - ease(seg(t, T_BACK, T_BACK + 0.5)))
    lean += 6 * go
    dx += 34 * go
    smile += 0.15 * go
    if go > 0.02:  # his hand comes up, unsure
        hand_up = go * (1 - seg(t, T_HESIT + 0.25, T_BACK))
        arm_l = dict(wrist=lerp2(POCKET, (880.0, 1420.0), hand_up), hand="open" if hand_up > 0.5 else "pocket", ang=-70, spread=0.6, curl=0.3,
                     elbow=(0.6, 1.0))
    stuck = seg(t, T_HESIT, T_HESIT + 0.2) * (1 - seg(t, T_BACK, T_BACK + 0.4))
    worry += 0.8 * stuck
    smile -= 0.35 * stuck
    brow += 0.2 * stuck
    down = seg(t, T_BACK + 0.3, T_BACK + 0.8)
    pitch -= 13 * down
    gy += 0.85 * down
    shrug += 0.35 * down
    # he turns his phone over to look at it: its light on his face
    flip = ease(seg(t, T_FLIP, T_FLIP + 0.45))
    ph["turn"] = 180 * flip
    ph["cy"] = PHONE["cy"] - 60 * flip
    ph["angle"] = PHONE["angle"] - 10 * flip
    lift = 0.65 * flip

    # « Qui ose pas poser de questions. »: his hand half up, as in class; it falls back
    r_up = back(seg(t, T_RAISE, T_RAISE + 0.35), 1.4) * (1 - ein(seg(t, T_DROP, T_DROP + 0.22)))
    if r_up > 0.01:
        arm_l = dict(wrist=lerp2(POCKET, (905.0, 1120.0), r_up), hand="open" if r_up > 0.4 else "pocket", ang=-86, spread=0.5, curl=0.45,
                     elbow=(0.3, 1.0))
        pitch += 10 * r_up * (1 - down * 0.5)
        gy -= 0.8 * r_up
        gx += 0.4 * r_up
        worry += 0.3 * r_up
    # « Peut-être par peur de dire n'importe quoi… »: he opens his mouth, words come out; he shuts it
    say = seg(t, T_SAY - 0.1, T_SAY + 0.15) * (1 - seg(t, T_CRUMPLE - 0.1, T_CRUMPLE + 0.1))
    opn += 0.42 * say * (0.75 + 0.25 * math.sin(t * 19))
    pitch += 12 * seg(t, T_SAY - 0.3, T_SAY) * (1 - seg(t, L[6] - 0.2, L[6] + 0.2)) * down
    gy -= 0.9 * seg(t, T_SAY - 0.3, T_SAY) * (1 - seg(t, T_FALL - 0.1, T_FALL + 0.2)) * down
    fall_look = seg(t, T_FALL, T_FALL + 0.3) * (1 - seg(t, L[6], L[6] + 0.3))
    gy += 0.9 * fall_look
    gx -= 0.3 * fall_look
    worry += 0.4 * seg(t, T_CRUMPLE, T_CRUMPLE + 0.2)
    # « …ou peut-être par peur de déranger. »: he types, he rubs it out; he lets out a breath
    sigh = bump(t, T_ERASE + 0.55, 0.9)
    shrug -= 0.3 * sigh
    # « Depuis tout jeune… »: he looks up, at us
    up_ = seg(t, L[7] - 0.1, L[7] + 0.3)
    pitch = lerp(pitch, 3.0, up_)
    gy = lerp(gy, -0.1, up_)
    gx = lerp(gx, 0.0, up_)
    worry = lerp(worry, 0.6, up_)
    smile = lerp(smile, -0.1, up_)

    P.update(yaw=yaw, pitch=pitch, roll=roll, lean=lean, shrug=max(0.0, shrug), x=540.0 + dx, lift=lift, phone=ph, arm_l=arm_l,
             arm_r=dict(wrist=(ph["cx"] + 10, ph["cy"] + 140), hand="none", elbow=(-0.4, 1), k2=0.45))
    P["ex"] = dict(ex, gx=max(-1, min(1, gx)), gy=max(-1, min(1, gy)), smile=smile, open=opn, brow=brow, worry=max(0.0, worry))
    return P


def lens_center(P, side=-1):
    """Where the centre of one of his lenses is (the world), and how big it is."""
    hd = rig.head_of(P)
    f = rig.TONY
    ex0, ey0 = f["eye"]
    zp = float(hd.zf(ex0, ey0)) + 13
    c = hd.P3(np.array([[side * (ex0 + 2), ey0 - 1, zp]]))[0][0]
    return c, (f["eye_w"] + 13) * hd.s


# --- small drawings
OUTLINE = __import__("json").loads((ROOT / "assets/rise_logo_outline.json").read_text())


def draw_rise(cv, key, cx, cy, width, p):
    """RISE, drawn by hand from the real logo's outlines: the letters, hatched inside; the flame in orange."""
    if p <= 0:
        return
    x0, y0 = cx - width / 2, cy - OUTLINE["aspect"] * width / 2

    def at(q):
        return (x0 + q[0] * width, y0 + q[1] * width)
    pen = cv.pen(key + "rise")
    with drawing(seg(p, 0, 0.6)):
        for ctr in OUTLINE["letters"]:
            pen.line([at(q) for q in ctr] + [at(ctr[0])], w=2.8, amp=0.7)
    hp = seg(p, 0.4, 1.0)
    if hp > 0:
        polys = [[at(q) for q in ctr] for ctr in OUTLINE["letters"]]
        ink.hatch(cv.white, polys, ink.flat(0.8), cv.rng(key + "rh"), angle=-58, gap=6.5, lo=0.3, wmax=1.7, cross=0, prog=hp, evenodd=True)
    fp = seg(p, 0.55, 1.0)
    if fp > 0:
        op = cv.pen(key + "flame", "orange")
        with drawing(fp):
            for ctr in OUTLINE["flame"]:
                pts = [at(q) for q in ctr]
                op.line(pts + pts[:1], w=3.0, amp=0.6)
                mx = sum(q[0] for q in pts) / len(pts)
                my = sum(q[1] for q in pts) / len(pts)
                inner = [(mx + (x - mx) * 0.5, my + (y - my) * 0.5 + width * 0.004) for x, y in pts]
                op.line(inner + inner[:1], w=2.2, amp=0.5)


def bubble(cv, key, cx, cy, w, h, tail, p=1.0, lines=2, scale=1.0, lw=3.2, dots=0):
    """A speech bubble, its tail toward `tail`, words as scribbles (lines) or dots; scale pops it."""
    if p <= 0 or scale <= 0.02:
        return
    w, h = w * scale, h * scale
    pen = cv.pen(key + "bub")
    ring = [(cx + w / 2 * math.cos(a), cy + h / 2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 56)]
    ang = math.atan2(tail[1] - cy, tail[0] - cx)
    b0 = (cx + w * 0.36 * math.cos(ang - 0.28), cy + h * 0.36 * math.sin(ang - 0.28))
    b1 = (cx + w * 0.36 * math.cos(ang + 0.28), cy + h * 0.36 * math.sin(ang + 0.28))
    tl = (cx + (tail[0] - cx) * scale, cy + (tail[1] - cy) * scale)
    cv.solid(ring)
    cv.solid([b0, tl, b1])
    with drawing(p):
        pen.line(ring, w=lw, amp=0.6)
        pen.line([b0, tl, b1], w=lw * 0.9, amp=0.4)
        for i in range(lines):
            ly = cy - h * 0.18 + i * h * 0.3 / max(1, lines - 1) if lines > 1 else cy
            n = 11 if i < lines - 1 else 7
            pts = [(cx - w * 0.3 + j * w * 0.6 / 11, ly + 4 * scale * math.sin(j * 1.9 + cx * 0.1 + i)) for j in range(n)]
            pen.line(pts, w=2.2, amp=0.9)
    for i in range(dots):
        cv.disc(cx - w * 0.18 + i * w * 0.18, cy, 7 * scale)


def written(cv, key, strokes, p, w=3.0, layer="white", outline=0.0, amp=0.5):
    """Strokes (world points) written to progress p; with an outline, a black edge first (to read on top)."""
    if p <= 0:
        return None
    part, tip = letters.written(strokes, p)
    if outline:
        pb = cv.pen(key + "o")
        for s_ in part:
            if len(s_) > 1:
                _line(pb, s_, w + outline, amp, 0)
    pen = cv.pen(key, layer)
    for s_ in part:
        if len(s_) > 1:
            _line(pen, s_, w, amp)
        elif len(s_) == 1:
            cv.disc(s_[0][0], s_[0][1], w * 0.55, 255, layer)
    return tip


def text_strokes(text, font, size, x, y, align="left", slant=0.0, hand=1.0, seed=0):
    st, wd = letters.layout(text, font, size, slant, hand=hand, seed=seed)
    x0 = x - (wd / 2 if align == "center" else 0)
    return [[(x0 + a, y + b) for a, b in s_] for s_ in st]


def arrow(cv, key, pts, p, w=3.0):
    pen = cv.pen(key)
    pts = ink.smooth(pts, n=8)
    with drawing(seg(p, 0, 0.8)):
        pen.line(pts, w=w, amp=0.5)
    if p > 0.8:
        (x1, y1), (x0, y0) = pts[-1], pts[-4]
        a = math.atan2(y1 - y0, x1 - x0)
        with drawing(seg(p, 0.8, 1.0)):
            pen.line([(x1 - 26 * math.cos(a - 0.5), y1 - 26 * math.sin(a - 0.5)), (x1, y1), (x1 - 26 * math.cos(a + 0.5), y1 - 26 * math.sin(a + 0.5))],
                     w=w, amp=0.3)


def sweat(cv, key, x, y, s, p):
    if p <= 0:
        return
    drop = [(x + s * 14 * math.sin(a) * (1 - math.cos(a)) * 0.9, y - s * 30 * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 30)]
    cv.solid(drop)
    with drawing(p):
        cv.pen(key).line(drop, w=2.6, amp=0.3)
        cv.pen(key + "g").line([(x - 4 * s, y + 6 * s), (x - 5 * s, y + 14 * s)], w=2.2, amp=0.2)


def qmark(cv, key, x, y, size, p, w=6.0):
    st = text_strokes("?", "futural", size, x, y, "center", hand=0.6, seed=3)
    written(cv, key, st, p, w=w)


# --- the others, at the party Tony doesn't dare join
GROUP = [(1190.0, 985.0, rig.ADULT_W, 24, 0.0), (1410.0, 970.0, rig.ADULT_B, 0, 1.7), (1630.0, 988.0, rig.ADULT_M, -26, 3.1)]


def group_at(cv, t, p):
    for k, (x, y, face, yaw, ph) in enumerate(GROUP):
        talk = max(0.0, math.sin(t * 7 + ph * 2))
        laugh = bump((t + ph * 0.37) % 2.6, 0.0, 0.8)
        G = tony_pose(x=x, y=y - 10 * laugh, s=1.0, face=face, head_k=1.12, yaw=yaw + 6 * math.sin(t * 1.3 + ph), pitch=6 * laugh,
                      roll=4 * math.sin(t * 2 + ph), ex=dict(open=0.35 * talk + 0.3 * laugh, smile=0.6 + 0.4 * laugh, squint=0.6 * laugh,
                                                              gx=0.6 if yaw > 0 else -0.6, blink=bump((t + ph) % 3.1, 0, 0.25)),
                      outfit="shirt" if k == 1 else "tee", cloth=1.2)
        cup_y = y + 330 - 40 * bump((t + ph * 0.5) % 4.0, 0.0, 1.0)  # a cup in one hand, raised now and then
        G["arm_r"] = dict(wrist=(x - 70, cup_y + 60), hand="fist", ang=-75, elbow=(-1, 0.6), k2=0.6)
        G["arm_l"] = dict(wrist=(x + 125, y + 560), hand="pocket", elbow=(1, 0.4))
        if k == 0:  # she talks with her hand
            G["arm_l"] = dict(wrist=(x + 150 + 20 * math.sin(t * 3), y + 330), hand="open", ang=-50, spread=0.8, curl=0.3, elbow=(1, 1))
        with drawing(p):
            draw_tony(cv, f"g{k}", G, prog=p)
            cup = [(x - 98, cup_y - 44), (x - 42, cup_y - 44), (x - 48, cup_y + 34), (x - 92, cup_y + 34)]
            cv.solid(cup)
            ink.hatch(cv.white, [cup], ink.flat(0.6), cv.rng(f"cup{k}"), angle=80, gap=6, lo=0.3, wmax=1.5, cross=0, prog=p)
            cv.pen(f"cup{k}").line(cup + cup[:1], w=2.4, amp=0.3)


# --- the classroom, years ago
BOARD = [(170.0, 420.0), (910.0, 420.0), (910.0, 830.0), (170.0, 830.0)]
DESK = [(190.0, 1500.0), (890.0, 1500.0), (950.0, 1592.0), (130.0, 1592.0)]
Q_DESK = [(440.0, 1512.0), (650.0, 1508.0), (668.0, 1574.0), (426.0, 1580.0)]
KID = dict(x=540.0, y=1268.0, s=1.12, face=rig.KID, head_k=1.6, build=0.74)
QC = [(110.0, 520.0), (970.0, 520.0), (970.0, 1560.0), (110.0, 1560.0)]  # the report card filling the screen
CARD_W, CARD_H = 860.0, 1040.0


def kid_at(t):
    shame = seg(t, T_MATES + 0.3, T_MATES + 0.8) * 0.35 + seg(t, T_TEACH + 0.35, T_TEACH + 0.7) * 0.3 + seg(t, T_CLOSE + 0.2, T_CLOSE + 0.9) * 0.45
    P = tony_pose(**KID)
    P.update(pitch=-12 - 14 * shame, shrug=0.4 + 0.9 * shame, yaw=-6 * math.sin(t * 0.7), breath=0.5 + 0.5 * math.sin(t * 2.2))
    P["y"] = KID["y"] + 26 * shame
    P["ex"] = dict(gy=0.85, gx=0.25 * math.sin(t * 0.9) - 0.45 * bump(t, T_MATES + 0.2, 0.9) + 0.4 * bump(t, T_TEACH + 0.4, 0.8),
                   worry=0.4 + 0.6 * shame, blink=0.15 + 0.5 * shame + bump((t - 0.4) % 2.9, 0, 0.25), smile=-0.2 - 0.3 * shame)
    P["arm_r"] = dict(wrist=(478.0, 1530.0 + 10 * shame), hand="fist", ang=12, elbow=(-1, 0.5), k2=0.55)
    P["arm_l"] = dict(wrist=(604.0, 1528.0 + 10 * shame), hand="fist", ang=168, elbow=(1, 0.5), k2=0.55)
    return P


def chalk(cv, t, p):
    pen = cv.pen("board")
    with drawing(p):
        pen.line(BOARD + BOARD[:1], w=4.5)
        pen.line([(150, 400), (930, 400), (930, 850), (150, 850), (150, 400)], w=3.0)
        pen.line([(140, 870), (940, 870)], w=4.0)
        pen.line([(140, 886), (940, 886)], w=2.4)
    ink.hatch(cv.white, [BOARD], ink.flat(0.36), cv.rng("dust"), angle=-30, gap=11, lo=0.3, wmax=1.0, cross=0, prog=p)
    words = [("Contrôle", "scripts", 48, 250, 510), ("3 x + 5 = 20", "futural", 34, 250, 610), ("x = ?", "futural", 34, 250, 680),
             ("Dictée", "scripts", 44, 600, 510)]
    for i, (w_, f, sz, x, y) in enumerate(words):
        written(cv, f"ch{i}", text_strokes(w_, f, sz, x, y, hand=1.2, seed=i + 7), seg(p, 0.3 + 0.1 * i, 0.7 + 0.1 * i), w=2.6, amp=0.9)
    for i in range(4):  # the dictation's lines, too far to read
        y = 580 + i * 52
        pts = [(600 + j * 22, y + 5 * math.sin(j * 1.7 + i)) for j in range(12)]
        with drawing(seg(p, 0.6, 1.0)):
            pen.line(pts, w=2.0, amp=1.0)


def classroom(cv, t, p=1.0):
    """The classroom (its world): the board, the shadows of those close to him, the teacher, the others,
    the boy at his desk with the report card in front of him."""
    chalk(cv, t, p)
    rise = eout(seg(t, T_CLOSE, T_CLOSE + 0.75))
    if rise > 0:
        with drawing(p):
            draw_shadow(cv, "rel1", 300.0, 830.0, 1.22, rim_side=-1, rise=rise, prog=p)
            draw_shadow(cv, "rel2", 790.0, 800.0, 1.32, rim_side=1, rise=eout(seg(t, T_CLOSE + 0.2, T_CLOSE + 0.95)), prog=p)
    tp = min(p, seg(t, T_TEACH, T_TEACH + 0.45))
    if tp > 0:
        point = back(seg(t, T_TEACH + 0.35, T_TEACH + 0.65), 2.2)
        T = tony_pose(x=205.0, y=880.0, s=1.12, face=rig.TEACHER, head_k=1.05, outfit="shirt", yaw=lerp(-30, 26, ease(seg(t, T_TEACH + 0.2, T_TEACH + 0.5))),
                      pitch=-6, ex=dict(brow=-0.7 * point, worry=0.0, smile=-0.4, gx=0.5, gy=0.3, blink=0.25), cloth=1.1)
        T["arm_l"] = dict(wrist=lerp2((250.0, 1360.0), (470.0, 960.0), point), hand="point" if point > 0.3 else "fist", ang=lerp(80, 18, point),
                          elbow=(0.2, 1.0))
        T["arm_r"] = dict(wrist=(120.0, 1420.0), hand="fist", ang=100, elbow=(-1, 0.3))
        with drawing(tp):
            draw_tony(cv, "teacher", T, prog=tp)
    mp = min(p, seg(t, T_MATES, T_MATES + 0.4))
    HA = []
    if mp > 0:
        for k, (x, face, yaw, ph) in enumerate(((890.0, rig.MATE_A, -26, 0.0), (225.0, rig.MATE_B, 26, 1.1))):
            ha = abs(math.sin((t - T_MATES) * 9 + ph)) * seg(t, T_MATES + 0.3, T_MATES + 0.5)
            M = tony_pose(x=x, y=1265.0 - 16 * ha, s=0.8, face=face, head_k=1.55, build=0.75, yaw=yaw, pitch=8 + 10 * ha, roll=(-1) ** k * 6 * ha,
                          ex=dict(squint=0.9 * min(1, ha * 2), open=0.25 + 0.4 * ha, smile=1.0, gx=-0.7 if yaw < 0 else 0.7), cloth=1.1)
            if k == 0:
                M["arm_r"] = dict(wrist=(760.0, 1180.0 + 10 * ha), hand="point", ang=200, elbow=(0.4, 1), k1=0.8)
            with drawing(mp):
                draw_tony(cv, f"mate{k}", M, prog=mp)
            HA.append((k, x, ha))
    for k, x, ha in HA:  # their laughter, over everyone
        if ha > 0.05:
            written(cv, f"ha{k}", text_strokes("ha ha", "futural", 40, x + (-1) ** k * 30, 905 - 30 * ha, "center", hand=1.6, seed=k + int(t * 6) % 3),
                    p, w=3.4, outline=7.0)
    K = kid_at(t)
    with drawing(p):
        draw_tony(cv, "kid", K, prog=p, parts=("body", "head"))
    pen = cv.pen("desk")
    cv.solid(DESK + [(950.0, 1920.0), (130.0, 1920.0)][::-1])
    with drawing(p):
        pen.line(DESK + DESK[:1], w=4.0)
        pen.line([(136, 1592), (136, 1920)], w=4.0)
        pen.line([(944, 1592), (944, 1920)], w=4.0)
    ink.hatch(cv.white, [[(136.0, 1596.0), (944.0, 1596.0), (944.0, 1920.0), (136.0, 1920.0)]], ink.flat(0.42), cv.rng("deskh"), angle=4, gap=10,
              lo=0.3, wmax=1.4, cross=0, prog=p)
    with drawing(p):
        draw_tony(cv, "kid", K, prog=p, parts=("arms",))


# --- the report card: drawn into any four corners (on the desk, filling the screen)
SUBJECTS = [("Français", "7"), ("Mathématiques", "5,5"), ("Histoire-Géo", "8"), ("Anglais", "6,5")]
INK = ["Tony se complaît", "dans sa médiocrité."]


def qpt(Q, u, w):
    s_, t_ = u / CARD_W, w / CARD_H
    a = lerp2(Q[0], Q[1], s_)
    b = lerp2(Q[3], Q[2], s_)
    return lerp2(a, b, t_)


def card_strokes(text, font, size, u, w, slant=0.0, hand=1.0, seed=0):
    """Text in card units (u across, w down to its baseline)."""
    st, wd = letters.layout(text, font, size, slant, hand=hand, seed=seed)
    return [[(u + a, w + b) for a, b in s_] for s_ in st], wd


RED_STROKES = []
_size = min(74.0, 74.0 * 700 / max(letters.width(x, "scripts", 74) for x in INK))
for _i, _line_ in enumerate(INK):
    _st, _ = card_strokes(_line_, "scripts", _size, 70 + 26 * _i, 775 + _i * 125, slant=0.12, hand=0.9, seed=40 + _i)
    RED_STROKES += _st


def card(cv, Q, ink_p, detail=1.0):
    """The report card in the screen corners Q (no camera); the red ink written to ink_p. Its pen's tip."""
    hq = (Q[3][1] - Q[0][1] + Q[2][1] - Q[1][1]) / 2
    cv.solid(Q)
    pen = cv.pen("card")
    pen.line(list(Q) + [Q[0]], w=3.2, amp=0.5)

    def M(st):
        return [[qpt(Q, a, b) for a, b in s_] for s_ in st]
    k = hq / CARD_H
    if hq < 70:
        for w0 in (130, 300, 450, 620, 760, 880):
            pen.line([qpt(Q, 60, w0), qpt(Q, 800, w0)], w=1.6, amp=0.3)
        return None
    pen.line([qpt(Q, 40, 130), qpt(Q, 820, 130)], w=2.4, amp=0.4)
    for i in range(5):
        y = 210 + i * 80
        pen.line([qpt(Q, 40, y), qpt(Q, 820, y)], w=1.5, amp=0.4)
    pen.line([qpt(Q, 600, 210), qpt(Q, 600, 530)], w=1.6, amp=0.4)
    box = [qpt(Q, 40, 580), qpt(Q, 820, 580), qpt(Q, 820, 990), qpt(Q, 40, 990)]
    pen.line(box + box[:1], w=2.0, amp=0.4)
    if detail > 0 and hq > 160:
        tw = max(1.4, 2.6 * k)
        st, wd = card_strokes("BULLETIN SCOLAIRE", "futural", 46, 0, 100, hand=0.8, seed=1)
        written(cv, "cardh", M([[(a + (CARD_W - wd) / 2, b) for a, b in s_] for s_ in st]), 1.0, w=tw * 1.25)
        st, _ = card_strokes("Élève : Tony", "futural", 26, 60, 180, hand=0.8, seed=2)
        written(cv, "carde", M(st), 1.0, w=tw)
        for i, (m, n) in enumerate(SUBJECTS):
            st, _ = card_strokes(m, "futural", 30, 60, 270 + i * 80, hand=0.9, seed=10 + i)
            written(cv, f"cs{i}", M(st), 1.0, w=tw)
            st, _ = card_strokes(f"{n} / 20", "futural", 30, 640, 270 + i * 80, hand=0.9, seed=20 + i)
            written(cv, f"cn{i}", M(st), 1.0, w=tw)
        st, _ = card_strokes("Appréciation du professeur principal :", "futural", 24, 60, 630, hand=0.8, seed=30)
        written(cv, "cap", M(st), 1.0, w=tw * 0.9)
    tip = None
    if ink_p > 0:
        tip = written(cv, "red", M(RED_STROKES), ink_p, w=max(1.5, 4.2 * k), layer="red", amp=0.35)
    return tip


def pen_hand(cv, tip, t, prog=1.0):
    """The teacher's hand writing: the pen's red tip at `tip`, the pen held between the thumb and the
    index finger, the other fingers folded under it, the cuff and the sleeve away down to the right."""
    a = math.atan2(0.86, 0.5)  # up the pen, toward the hand
    ca, sa = math.cos(a), math.sin(a)
    tx, ty = tip

    def F(u, v):  # the pen's frame: u up the pen from its tip, v across it (to the right of it)
        return (tx + u * ca - v * sa, ty + u * sa + v * ca)

    def poly(pts):
        return [F(u, v) for u, v in ink.smooth(pts, closed=True, n=5)]
    pen = cv.pen("penhand")
    rng = cv.rng("penhand")
    # the sleeve and its cuff
    sleeve = [F(330, -95), F(900, -170), F(900, 190), F(330, 110)]
    cv.solid(sleeve)
    ink.hatch(cv.white, [sleeve], ink.cylinder(*F(330, 0), *F(900, 0), 150, amb=0.04), rng, angle=math.degrees(a) + 90, gap=6.5, lo=0.34, wmax=1.6,
              cross=0)
    pen.line([F(330, -95), F(900, -170)], w=2.6, amp=0.5)
    pen.line([F(330, 110), F(900, 190)], w=2.2, amp=0.5)
    cuff = [F(300, -100), F(350, -105), F(350, 118), F(300, 112)]
    cv.solid(cuff)
    pen.line(cuff + cuff[:1], w=2.4, amp=0.4)
    # the back of the hand
    back_ = poly([(300, -88), (205, -84), (130, -52), (112, -8), (150, 40), (210, 78), (300, 95)])
    cv.solid(back_)
    ink.hatch(cv.white, [back_], ink.sphere(*F(210, -20), 120, 120, amb=0.06), rng, angle=math.degrees(a) + 70, gap=5.5, lo=0.3, wmax=1.9,
              cross=0.8)
    pen.line(back_ + back_[:1], w=2.6, amp=0.4)
    # the folded fingers under the pen
    for k, (u0, v0) in enumerate(((150, 52), (190, 72))):
        f = poly([(u0 + 34, v0 - 18), (u0 - 22, v0 - 14), (u0 - 30, v0 + 10), (u0 + 30, v0 + 26)])
        cv.solid(f)
        ink.hatch(cv.white, [f], ink.flat(0.5), rng, angle=math.degrees(a), gap=5.5, lo=0.3, wmax=1.5, cross=0)
        pen.line(f + f[:1], w=2.0, amp=0.3)
    # the pen: its body, its grip, its red tip
    body = poly([(16, -6), (330, -13), (330, 13), (16, 6)])
    cv.solid(body)
    ink.hatch(cv.white, [body], ink.flat(0.55), rng, angle=math.degrees(a) + 90, gap=5.0, lo=0.3, wmax=1.4, cross=0)
    pen.line(body + body[:1], w=2.2, amp=0.3)
    cone = [F(0, 0), F(18, -6), F(18, 6)]
    cv.solid(cone)
    cv.pen("pentip", "red").line(cone + cone[:1], w=3.0, amp=0.2)
    # the thumb along its side, the index finger over it
    thumb = poly([(70, 22), (170, 34), (170, 66), (78, 40)])
    cv.solid(thumb)
    ink.hatch(cv.white, [thumb], ink.flat(0.62), rng, angle=math.degrees(a) + 80, gap=5.0, lo=0.3, wmax=1.6, cross=0)
    pen.line(thumb + thumb[:1], w=2.2, amp=0.3)
    index = poly([(56, -10), (190, -40), (200, -78), (62, -34)])
    cv.solid(index)
    ink.hatch(cv.white, [index], ink.cylinder(*F(56, -22), *F(200, -58), 20, amb=0.06), rng, angle=math.degrees(a) + 80, gap=5.0, lo=0.3,
              wmax=1.8, cross=0)
    pen.line(index + index[:1], w=2.4, amp=0.3)
    pen.line([F(70, -26), F(82, -30)], w=1.4, amp=0.2)  # its nail
    pen.line([F(132, -22), F(136, -46)], w=1.3, amp=0.2)  # its knuckle


# --- the camera, and the picture at time t
def camera_tony(t):
    """(zoom, world point at the screen's centre) in Tony's world."""
    z = kf(t, [(T_PULL[0], 3.9), (T_PULL[1], 1.0), (L[2] - 0.1, 1.0), (L[2] + 0.5, 1.06), (T_WIDE[0], 1.06), (T_WIDE[1], 0.64),
               (L[4] - 0.1, 0.64), (L[4] + 0.75, 1.0), (L[6] - 0.1, 1.0), (L[6] + 0.6, 1.1)])
    c = kf(t, [(T_PULL[0], (PHONE["cx"], PHONE["cy"] - 10)), (T_PULL[1], (540.0, 1065.0)), (L[2] - 0.1, (540.0, 1065.0)), (L[2] + 0.5, (540.0, 1030.0)),
               (T_WIDE[0], (540.0, 1030.0)), (T_WIDE[1], (960.0, 1090.0)), (L[4] - 0.1, (960.0, 1090.0)), (L[4] + 0.75, (540.0, 1065.0)),
               (L[6] - 0.1, (540.0, 1065.0)), (L[6] + 0.6, (505.0, 1110.0))])
    if t < T_PULL[1] and t > T_PULL[0]:  # backing away: the zoom in log space, the centre tied to it
        u = ease(seg(t, *T_PULL))
        z = math.exp(lerp(math.log(3.9), 0.0, u))
        c = lerp2((540.0, 1065.0), (PHONE["cx"], PHONE["cy"] - 10), (z - 1) / 2.9)  # the centre tied to the zoom
    return z, c


def cv_inside(poly, q):
    """Is the point q inside the polygon (even-odd)?"""
    x, y = q
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


LENS_R = 1500.0  # the lens' radius on the screen when the classroom fills it at its own scale


def lens_push(t, P):
    """In the lens: (tony zoom, centre), from the moment the camera goes for his glasses."""
    z0, c0 = camera_tony(T_LENS[0])
    lc, _ = lens_center(P)
    u = seg(t, *T_LENS)
    uz = ease(u) ** 1.3
    z = math.exp(lerp(math.log(z0), math.log(30.0), uz))
    c = lerp2(c0, tuple(lc), eout(min(1.0, u * 1.7)))
    return z, c


def phone_screen(t):
    def screen(cv, fr):
        cx, cy = fr["P"](0, -0.08)
        draw_rise(cv, "r1", cx, cy, fr["w"] * 0.66, seg(t, 0.25, 1.5))
    return screen


def world_tony(cv, t, v):
    """Tony's world: him, and what each phrase brings."""
    P = tony_at(t)
    if t >= T_WIDE[0] - 0.1:
        group_at(cv, t, seg(t, T_WIDE[0] + 0.1, T_WIDE[0] + 1.0))
        for k, (bx, by, tx, ty, at) in enumerate(((1240.0, 640.0, 1215.0, 740.0, 0.6), (1600.0, 625.0, 1630.0, 730.0, 1.5))):
            sc = back(seg(t, T_WIDE[0] + at, T_WIDE[0] + at + 0.3))
            bubble(cv, f"gb{k}", bx, by, 170, 90, (tx, ty), 1.0, lines=2, scale=sc * (1 + 0.04 * math.sin(t * 5 + k)))
    with drawing(seg(t, 0.0, 0.5)):  # the very first drawings: his phone and his hand draw themselves
        info = draw_tony(cv, "tony", P, screen=phone_screen(t), prog=seg(t, 0.0, 0.5))
    # the others' words, all round him
    talk_off = seg(t, L[2] - 0.15, L[2] + 0.2)
    for k, (bx, by, tx, ty, w_, h_, n) in enumerate(((175.0, 520.0, -60.0, 470.0, 230, 110, 2), (905.0, 470.0, 1140.0, 420.0, 220, 100, 2),
                                                     (150.0, 930.0, -80.0, 960.0, 200, 96, 1), (930.0, 880.0, 1160.0, 920.0, 210, 104, 2),
                                                     (880.0, 1310.0, 1160.0, 1350.0, 200, 96, 1))):
        at = T_TALK + 0.12 * k
        sc = back(seg(t, at, at + 0.28))
        if sc > 0 and talk_off < 1:
            bubble(cv, f"tb{k}", bx, by, w_, h_, (tx, ty), 1 - talk_off, lines=n, scale=sc * (1 + 0.03 * math.sin(t * 6 + k)))
    # his own: three dots, typing… then nothing
    mine_in = back(seg(t, T_TALK + 0.55, T_TALK + 0.8))
    mine_out = ein(seg(t, L[2] - 0.45, L[2] - 0.1))
    if mine_in > 0 and mine_out < 1:
        n_dots = min(3, int((t - T_TALK - 0.6) * 5)) if t > T_TALK + 0.6 else 0
        bubble(cv, "mine", 740.0, 880.0, 150, 84, (650.0, 930.0), 1.0, lines=0, scale=mine_in * (1 - mine_out), dots=max(0, n_dots))
    # « Tony », written by him, an arrow to him
    lab_p = seg(t, T_WAVE + 0.2, T_WAVE + 0.9)
    lab_off = seg(t, L[3] - 0.1, L[3] + 0.25)
    if lab_p > 0 and lab_off < 1:
        k_ = lab_p * (1 - lab_off)
        written(cv, "name", text_strokes("Tony", "scripts", 92, 95, 520, slant=0.1, hand=0.8, seed=5), k_ if lab_off == 0 else 1 - lab_off, w=4.2)
        arrow(cv, "arrow", [(190, 560), (250, 640), (300, 690)], seg(t, T_WAVE + 0.7, T_WAVE + 1.0) * (1 - lab_off), w=3.4)
    # stuck: a drop of sweat
    hd = info["head"]
    sw = seg(t, T_HESIT + 0.05, T_HESIT + 0.25) * (1 - seg(t, T_BACK + 0.2, T_BACK + 0.4))
    if sw > 0:
        sx, sy = hd.P3(np.array([[96.0, -50.0, 20.0]]))[0][0]
        sweat(cv, "sweat", sx, sy + 40 * seg(t, T_HESIT + 0.25, T_BACK + 0.2), 1.8, sw)
    # the question he doesn't ask
    q_in = seg(t, T_RAISE + 0.25, T_RAISE + 0.6)
    if q_in > 0:
        fall = ein(seg(t, T_DROP, T_DROP + 0.5))
        qx, qy = 935.0 + 40 * fall, 850.0 + 860 * fall
        written(cv, "q", text_strokes("?", "futural", 150, qx, qy, "center", hand=0.4, seed=9), q_in * (1 - seg(t, T_DROP + 0.3, T_DROP + 0.55)), w=8.0)
    # « n'importe quoi »: words come out, tangled; the bubble crumples into a ball and drops
    if t > T_SAY - 0.05 and t < T_FALL + 0.9:
        mouth = hd.P3(np.array([[24.0, 60.0, 80.0]]))[0][0]
        grow = back(seg(t, T_SAY, T_SAY + 0.45))
        cr = ease(seg(t, T_CRUMPLE, T_FALL))
        bx, by = mouth[0] + 230 * grow, mouth[1] - 250 * grow
        if t > T_FALL:
            f_ = t - T_FALL
            bx += 130 * f_
            by += 0.5 * 4200 * f_ * f_
        rng = cv.rng("crumple")
        n = 40
        ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
        noise = rng.uniform(-1, 1, n)
        rw = (190 * (1 - cr) + 52 * cr) * grow
        rh = (140 * (1 - cr) + 50 * cr) * grow
        rr = 1 + noise * 0.22 * cr
        ring = [(bx + rw * r_ * math.cos(a), by + rh * r_ * math.sin(a)) for a, r_ in zip(ang, rr)]
        ring.append(ring[0])
        cv.solid(ring)
        pen = cv.pen("say")
        pen.line(ring, w=3.4, amp=0.5)
        if cr < 0.05:
            tail = [(bx - rw * 0.55, by + rh * 0.55), (mouth[0] + 20, mouth[1] - 10), (bx - rw * 0.25, by + rh * 0.85)]
            cv.solid(tail)
            pen.line(tail, w=3.0, amp=0.4)
        # the tangle of words inside
        tg = cv.rng("tangle")
        pts = [(bx + rw * 0.55 * math.cos(a) * tg.uniform(0.3, 1), by + rh * 0.5 * math.sin(a * 1.7) * tg.uniform(0.3, 1)) for a in np.linspace(0, 9 * math.pi, 46)]
        with drawing(seg(t, T_SAY + 0.15, T_CRUMPLE - 0.1)):
            pen.line(ink.smooth(pts, n=5), w=2.4, amp=1.0)
        for k in range(int(10 * cr)):  # its creases
            a0 = tg.uniform(0, 2 * math.pi)
            pen.line([(bx + rw * 0.2 * math.cos(a0), by + rh * 0.2 * math.sin(a0)), (bx + rw * 0.9 * math.cos(a0 + 0.4), by + rh * 0.9 * math.sin(a0 + 0.4))],
                     w=1.8, amp=0.6)
    return P, info


TYPED = "Désolé de te déranger…"


def typed_bubble(cv, t):
    """What he starts to write, and rubs out, letter by letter: a message above his phone."""
    a = seg(t, T_TYPE - 0.25, T_TYPE)
    if a <= 0 or t > T_ERASE + 1.1:
        return
    n = len(TYPED)
    k = int(n * seg(t, T_TYPE, T_TYPE + 1.0))
    if t > T_ERASE:
        k = int(n * (1 - seg(t, T_ERASE, T_ERASE + 0.65)))
    shrink = ein(seg(t, T_ERASE + 0.7, T_ERASE + 0.95))
    sc = back(a) * (1 - shrink)
    if sc <= 0.02:
        return
    x0, y0 = 355.0, 1105.0
    w_, h_ = 470 * sc, 86 * sc
    box = rig.rounded_rect(x0 + 160, y0, w_, h_, 34 * sc)
    cv.solid(box)
    pen = cv.pen("typed")
    pen.line(box + box[:1], w=3.0, amp=0.4)
    pen.line([(x0 + 160 - 18 * sc, y0 + h_ / 2), (x0 + 120, y0 + h_ / 2 + 44 * sc), (x0 + 160 + 10 * sc, y0 + h_ / 2)], w=2.8, amp=0.3)
    if sc > 0.9 and k > 0:
        st = text_strokes(TYPED[:k], "futural", 28, x0 + 160 - 205, y0 + 14, hand=0.6, seed=11)
        written(cv, "typedtxt", st, 1.0, w=2.6)
        cx = max(x for s_ in st for x, _ in s_) + 10 if st else x0 - 40
    else:
        cx = x0 - 40
    if sc > 0.9 and int(t * 4) % 2 == 0:  # the caret
        pen.line([(cx, y0 - 20), (cx, y0 + 18)], w=2.6, amp=0.2)


def picture(t, v):
    """The drawing at time t (variant v of its boil): RGB."""
    if t < T_LENS[0]:
        z, c = camera_tony(t)
        cv = Canvas(v)
        with cam(z, c):
            world_tony(cv, t, v)
            typed_bubble(cv, t)
        return cv.picture()
    if t < T_LENS[1]:
        return lens_picture(t, v)
    return class_picture(t, v)


def lens_picture(t, v):
    """The camera going into his lens: him outside it, the classroom inside it, drawing itself."""
    P = tony_at(t)
    z, c = lens_push(t, P)
    cv = Canvas(v)
    with cam(z, c):
        hd = rig.head_of(P)
        f = rig.TONY
        ex0, ey0 = f["eye"]
        zp = float(hd.zf(ex0, ey0)) + 13
        th = np.linspace(0, 2 * math.pi, 120)
        rx, ry = f["eye_w"] + 13, f["eye_h"] + 17
        lens = hd.P3(np.column_stack([-(ex0 + 2) + rx * np.cos(th), ey0 - 1 + ry * np.sin(th), np.full_like(th, zp)]))[0]
        ls = ink.to_screen(lens)
        covered = all(cv_inside(ls, q) for q in ((0, 0), (W, 0), (0, H), (W, H)))
        if not covered:  # once the lens fills the screen, nothing of him shows any more
            world_tony(cv, t, v)
            typed_bubble(cv, t)
    out = cv.picture()
    lc = ls.mean(axis=0)
    r = float(np.mean(np.hypot(*(ls - lc).T)))
    if r < 30:
        return out
    cc = Canvas(v)
    with cam(r / LENS_R, (540.0, 1000.0), tuple(lc)):
        classroom(cc, t, seg(r, 30, 420))
    inside = cc.picture()
    m = Image.new("L", (W, H), 0)
    shrink = (ls - lc) * (1 - 3.0 / max(r, 1)) + lc
    ImageDraw.Draw(m).polygon([tuple(q) for q in shrink], fill=255)
    gone = seg(r, 60, 260)  # his eye, behind the lens, gives way to what he remembers
    if gone < 1:
        eye = Image.composite(out, Image.new("RGB", (W, H)), m).point(lambda x: int(x * (1 - gone)))
        inside = ImageChops.lighter(inside, eye)
    out.paste(inside, (0, 0), m)
    return out


def class_camera(t):
    """(zoom, centre, screen point) in the classroom, from the moment the lens has filled the screen."""
    P = tony_at(T_LENS[1])
    z_end = lens_push(T_LENS[1], P)[0]
    lc, lr = lens_center(P)
    r_end = lr * z_end
    z0 = r_end / LENS_R
    u = ease(seg(t, T_LENS[1], T_LENS[1] + 0.6))
    z = lerp(z0, 1.0, u)
    c = lerp2((540.0, 1000.0), (540.0, 960.0), u)
    return z, c


def class_picture(t, v):
    cv = Canvas(v)
    z, c = class_camera(t)
    du = seg(t, *T_DIVE)
    dive = ease(du)
    qdc = ((Q_DESK[0][0] + Q_DESK[2][0]) / 2, (Q_DESK[0][1] + Q_DESK[2][1]) / 2)
    zd = z * math.exp(math.log(5.2) * dive ** 1.2)
    cd = lerp2(c, qdc, eout(min(1.0, du * 1.4)))
    qd = lerp2((540.0, 960.0), (540.0, 1040.0), dive)
    with cam(zd, cd, qd):
        bg = 1.0 - seg(dive, 0.5, 0.95)  # as the paper comes up to us, the room rubs itself out round it
        if bg > 0:
            classroom(cv, t, bg)
        q_desk = [tuple(q) for q in ink.to_screen(Q_DESK)]
    Q = [lerp2(a, b, ease(seg(dive, 0.35, 1.0))) for a, b in zip(q_desk, QC)]
    ink_p = seg(t, *T_WRITE)
    with cam():
        tip = card(cv, Q, ink_p, detail=seg(dive, 0.5, 0.9))
        hand_in = eout(seg(t, T_WRITE[0] - 0.35, T_WRITE[0]))
        hand_out = ein(seg(t, T_WRITE[1] + 0.1, T_WRITE[1] + 0.45))
        if hand_in > 0 and hand_out < 1:
            if tip is None:
                tip = qpt(Q, 70, 690)
            off = (1 - hand_in) * 700 + hand_out * 800
            pen_hand(cv, (tip[0] + off * 0.6, tip[1] + off), t)
    return cv.picture()


# --- the words, written word by word (strokes, not a font)
CAP = dict(font="futural", size=46, line=72, top=205, width=950, w=5.2, edge=10.0)
_caps = {}


def caption(t, v):
    """The phrase being said, its words so far (the last one being written): (black edge, white ink) masks."""
    line = next((l for l in LINES if l["t0"] <= t < l["t1"]), None)
    if line is None:
        return None
    said = (t - line["t0"]) * WPS
    words = line["text"].split(" ")
    k = min(len(words), 1 + int(said))
    wp = 1.0 if said >= len(words) else clip01((said - (k - 1)) / 0.45)
    key = (line["text"], k, v, round(wp, 1))
    if key in _caps:
        return _caps[key]
    edge, white = Canvas(v), Canvas(v)
    lines = letters.wrap(line["text"], CAP["font"], CAP["size"], CAP["width"])
    n = 0
    with cam():
        for i, ln in enumerate(lines):
            ws = ln.split(" ")
            x = 540 - letters.width(ln, CAP["font"], CAP["size"]) / 2
            y = CAP["top"] + i * CAP["line"]
            for j, w_ in enumerate(ws):
                if n >= k:
                    break
                st = text_strokes(w_, CAP["font"], CAP["size"], x, y, hand=0.8, seed=zlib.crc32(w_.encode()) % 997 + j)
                p = wp if n == k - 1 else 1.0
                written(edge, f"e{i}{j}", st, p, w=CAP["w"] + CAP["edge"], amp=0.4)
                written(white, f"c{i}{j}", st, p, w=CAP["w"], amp=0.4)
                x += letters.width(w_ + " ", CAP["font"], CAP["size"])
                n += 1
    out = (edge.white.resize((W, H), Image.LANCZOS), white.white.resize((W, H), Image.LANCZOS))
    _caps[key] = out
    return out


def frame_at(t):
    v = int(t * DRAWINGS) % 3
    pic = picture(t, v)
    cap = caption(t, v)
    if cap is not None:
        pic.paste((0, 0, 0), (0, 0), cap[0])
        pic.paste((255, 255, 255), (0, 0), cap[1])
    return pic


def _render(args):
    g, d = args
    t = g / DRAWINGS
    frame_at(t).save(f"{d}/{g:05d}.png")
    return g


def main(until=END):
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    until = min(until, END)
    name = "episode1_v6_opening.mp4" if until >= END else f"episode1_v6_0-{until:g}s.mp4"
    n = int(until * DRAWINGS)
    with tempfile.TemporaryDirectory() as d:
        with Pool(4) as pool:
            for i, g in enumerate(pool.imap_unordered(_render, [(g, d) for g in range(n)], chunksize=2)):
                if i % 24 == 0:
                    print(f"{i}/{n}", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(DRAWINGS), "-i", f"{d}/%05d.png", "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                        "-shortest", "-movflags", "+faststart", str(out / name)], check=True)
    print(out / name, f"{until:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--until":
        main(float(sys.argv[2]))
    elif len(sys.argv) > 1:
        for s_ in sys.argv[1:]:
            tt = int(float(s_) * DRAWINGS) / DRAWINGS
            frame_at(tt).save(ROOT / f"still_{s_}.png")
    else:
        main()
