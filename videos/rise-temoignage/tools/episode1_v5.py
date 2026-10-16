"""Tony's testimony, episode 1, v5: a real drawn cartoon, not shots blended into each other.

What Tony asked: no transitions « between two videos »; every move a run of drawings, like an animator's.
- 12 drawings a second, each held two frames ("on twos"); every drawing is drawn again, so the lines boil.
- Camera moves are redrawn, not zoomed pictures: every point goes through draw_test's camera (draw_test.CAM).
  The schoolboy at his desk: the camera goes up to the paper on the desk, the paper rises to face us and
  fills the screen; the teacher's red ink writes itself; then the camera backs away from it and finds it
  lying on the table in front of Tony today, and keeps backing away as he makes himself small; later it
  backs away again until his shell is one among many.
- No dissolves: otherwise a shot's strokes rub themselves out and the next ones trace themselves.
- The words come one at a time, at the pace of speech, like his earlier testimony video.
- No music: only the boom under the logo, until his voice comes in.
Usage: python3 tools/episode1_v5.py [--until s] [t ...]  -> renders/episode1_v5.mp4 (or a part of it,
renders/episode1_v5_0-<s>s.mp4, to check the start before going on), or stills at the given times
"""
import math
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageChops, ImageDraw, ImageFont

import draw_test as dt
import episode1 as ep
import episode1_v3 as v3
import episode1_v4 as v4  # its pen draws strokes from their start (v4.PROG); its timeline; its small drawings
from draw_test import Pen, arc, bez

ROOT = v3.ROOT
W, H, S = 1080, 1920, dt.S
FPS, DRAWINGS = 24, 12  # twelve drawings a second, each one held for two frames
LINES, L, DURATION = v4.LINES, v4.L, v4.DURATION
OFF = 0.35  # the time a shot's strokes take to rub themselves out
SANS = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
SANS_B = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
CAVEAT = str(ROOT / "assets/fonts/caveat-latin-700-normal.woff")
HANDF = str(ROOT / "assets/fonts/patrick-hand-latin-400-normal.woff")
_fonts = {}


def font(path, px):
    k = (path, max(4, int(px)))
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, k[1])
    return _fonts[k]


def clip01(x):
    return min(1.0, max(0.0, x))


def ease(x):
    return v3.ease(x)


def lerp(a, b, u):
    return a + (b - a) * u


def lerp2(a, b, u):
    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u))


class cam:
    """The camera for what is drawn inside: zoom z, the drawing's point p lands on the screen at q."""

    def __init__(self, z=1.0, p=(540.0, 960.0), q=None):
        q = q or p
        self.v = [z, p[0], p[1], q[0], q[1]]

    def __enter__(self):
        self.old = dt.CAM[:]
        dt.CAM[:] = self.v
        return self

    def __exit__(self, *a):
        dt.CAM[:] = self.old


def seed(key):
    return zlib.crc32(key.encode()) % 100000


def drawn(c, key, v, p, fn):
    """One element, drawn at progress p (0 nothing, 1 every stroke whole) through the current camera."""
    if p <= 0:
        return None
    ck = (key, v, tuple(round(x, 3) for x in dt.CAM))
    if p >= 1 and ck in c:
        return c[ck]
    img = Image.new("L", (W * S, H * S), 0)
    pen = Pen(img, np.random.default_rng(seed(key) * 10 + v))
    v4.PROG[0] = min(1.0, p)
    fn(pen)
    v4.PROG[0] = 1.0
    out = img.resize((W, H), Image.LANCZOS)
    if p >= 1:
        c[ck] = out
    return out


def tony(c, v, p):
    """Tony at night, head in his hand (draw_test.draw), through the current camera, at progress p."""
    if p <= 0:
        return None
    ck = ("tony", v, tuple(round(x, 3) for x in dt.CAM))
    if p >= 1 and ck in c:
        return c[ck]
    v4.SHOW_BUBBLES[0] = False
    v4.PROG[0] = min(1.0, p)
    img = dt.draw(v, 0.0)
    v4.PROG[0] = 1.0
    v4.SHOW_BUBBLES[0] = True
    if p >= 1:
        c[ck] = img
    return img


def stack(*layers):
    base = Image.new("L", (W, H), 0)
    for la in layers:
        if la is not None:
            base = ImageChops.lighter(base, la)
    return base


def on(t, at, dur=0.6, until=None, off=0.3):
    """Draw-on from `at`; rubbed out over `off` before `until`."""
    p = clip01((t - at) / dur)
    if until is not None:
        p = min(p, clip01((until - t) / off))
    return p


def logo_pop(pic, t, at, x, y, w, off=1.0):
    """The RISE logo pops in (in steps, like the drawings), and out again as the shot rubs out."""
    s = (0.6 + 0.4 * ease((t - at) / 0.25)) * off if t >= at else 0
    if s < 0.15:
        return pic
    lg = v4.rise_logo(max(10, int(w * s)))
    if pic.mode != "RGB":
        pic = pic.convert("RGB")
    ImageDraw.Draw(pic).rectangle([x - lg.width // 2 - 8, y - lg.height // 2 - 8, x + lg.width // 2 + 8, y + lg.height // 2 + 8], fill=(0, 0, 0))
    pic.paste(lg, (x - lg.width // 2, y - lg.height // 2), lg)
    return pic


# --- the report card, drawn into any four corners (a paper on a desk, the whole screen, a paper on a table)
CARD_W, CARD_H = 860.0, 1000.0
QC = [(110, 540), (970, 540), (970, 1540), (110, 1540)]  # filling the screen
Q_DESK = [(470, 1345), (650, 1340), (660, 1400), (462, 1405)]  # on the schoolboy's desk (his drawing's place)
Q_TABLE = [(468, 1505), (742, 1490), (768, 1640), (448, 1652)]  # on Tony's table today (his drawing's place)
INK_LINES = ["Tony se complaît", "dans sa médiocrité."]
INK_N = sum(len(x) for x in INK_LINES)


def qpt(Q, u, w):
    """A point of the card (u across, w down, in card units) inside the corners Q."""
    s, t = u / CARD_W, w / CARD_H
    a = lerp2(Q[0], Q[1], s)
    b = lerp2(Q[3], Q[2], s)
    return lerp2(a, b, t)


def q_through_cam(Q):
    return [dt.T(*p) for p in Q]


def card(pen, red, Q, ink_n):
    """The report card in screen corners Q (drawn with no camera), its details only when it is big enough;
    the red ink, its first ink_n letters, onto `red` (a mask)."""
    hq = (Q[3][1] - Q[0][1] + Q[2][1] - Q[1][1]) / 2
    k = hq / CARD_H
    pen.line(Q + Q[:1], w=3.5)
    if hq < 60:
        if ink_n > 0:
            a, b = qpt(Q, 120, 720), qpt(Q, 700, 720)
            ImageDraw.Draw(red).line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=255, width=int(3 * S))
        return
    detail = clip01((hq - 140) / 260)
    for w0 in (120,):
        pen.line([qpt(Q, 40, w0), qpt(Q, 820, w0)], w=2.6)
    for i in range(4):
        y = 170 + i * 85
        pen.line([qpt(Q, 40, y + 62), qpt(Q, 820, y + 62)], w=1.6)
    pen.line([qpt(Q, 630, 150), qpt(Q, 630, 500)], w=1.8)
    box = [qpt(Q, 40, 600), qpt(Q, 820, 600), qpt(Q, 820, 950), qpt(Q, 40, 950)]
    pen.line(box + box[:1], w=2.2)
    if detail > 0.3 and v4.PROG[0] > 0.6:
        g = int(255 * clip01((detail - 0.3) / 0.4))
        d = pen.d

        def txt(u, w, s, size, path=SANS, fill=g):
            x, y = qpt(Q, u, w)
            d.text((x * S, y * S), s, font=font(path, size * k * S), fill=fill)
        txt(60, 40, "BULLETIN SCOLAIRE", 46, SANS_B)
        for i, (m, n) in enumerate([("Français", "7"), ("Mathématiques", "5,5"), ("Histoire-Géo", "8"), ("Anglais", "6,5")]):
            txt(60, 170 + i * 85, m, 34)
            txt(670, 170 + i * 85, n + " / 20", 34)
        txt(60, 540, "Appréciation du professeur principal", 30)
    if ink_n > 0 and hq >= 60:
        rd = ImageDraw.Draw(red)
        fnt = font(CAVEAT, 96 * k * S)
        n = ink_n
        for li, line in enumerate(INK_LINES):
            if n <= 0:
                break
            part = line[:n]
            n -= len(line)
            x, y = qpt(Q, 80, 640 + li * 120)
            rd.text((x * S, y * S), part, font=fnt, fill=255)


def card_layer(c, key, v, Q, ink_n, p=1.0):
    """The card as (white lines, red ink) at 1080x1920."""
    img = Image.new("L", (W * S, H * S), 0)
    red = Image.new("L", (W * S, H * S), 0)
    pen = Pen(img, np.random.default_rng(seed(key) * 10 + v))
    with cam():
        v4.PROG[0] = min(1.0, p)
        card(pen, red, Q, ink_n)
        v4.PROG[0] = 1.0
    return img.resize((W, H), Image.LANCZOS), red.resize((W, H), Image.LANCZOS)


def paper_mask(Q):
    """The paper hides what is under it."""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in Q], fill=255)
    return m


def under(bg, lines, Q):
    """The paper laid over a picture: blank inside its corners, then its own lines."""
    bg = Image.composite(Image.new("L", (W, H), 0), bg, paper_mask(Q))
    return ImageChops.lighter(bg, lines)


def colour(base_l, red=None):
    rgb = base_l.convert("RGB")
    if red is not None:
        rgb.paste((226, 40, 40), (0, 0), red)
    return rgb


# --- small drawings that go through the camera
def text_w(pen, x, y, s, size, path=HANDF):
    z = dt.CAM[0]
    X, Y = dt.T(x, y)
    if v4.PROG[0] > 0.5:
        pen.d.text((X * S, Y * S), s, font=font(path, size * z * S), fill=255)


def kid_desk(p):
    v4.person(p, 540, 1240, 1.6, glasses=True, w=4)
    for k in range(14):  # his hair
        a = math.radians(200 + k * 10)
        p.line([(540 + 60 * math.cos(a), 1092 + 64 * math.sin(a)), (540 + 64 * math.cos(a) + 6, 1092 + 68 * math.sin(a) - 22)], w=2)
    p.line([(200, 1330), (880, 1330)], w=5)
    p.line([(230, 1330), (230, 1600)], w=4)
    p.line([(850, 1330), (850, 1600)], w=4)


def friends(p):
    v4.person(p, 170, 1080, 1.0)
    v4.person(p, 320, 1040, 1.0)
    text_w(p, 110, 870, "ha ha", 46)


def teacher(p):
    v4.person(p, 900, 1010, 1.3, glasses=True)
    p.line([(840, 980), (720, 920), (690, 915)], w=4)


def close(p):
    v4.person(p, 380, 760, 1.5)
    v4.person(p, 700, 740, 1.5)


# --- the shots: each gives the picture (RGB) at drawing time t, variant v
def shot_hook(t, v, c, te):
    off = clip01((te - t) / OFF)
    els = [drawn(c, "phone", v, min(on(t, L[0], 0.8), off), lambda p: v4.phone_body(p, 540, 1180, 380, 720))]
    if t > L[0] + 0.9:
        els.append(drawn(c, "glow", v, min(on(t, L[0] + 0.9, 0.4), off), lambda p: v4.glow(p, 540, 1180, 400, 470, 80, 1.8)))
    for k, (x, y, w, h, side) in enumerate([(200, 560, 300, 130, -1), (860, 520, 290, 120, 1), (180, 860, 280, 115, -1),
                                            (880, 820, 270, 125, 1), (200, 1500, 270, 110, -1), (880, 1480, 280, 115, 1)]):
        els.append(drawn(c, f"chat{k}", v, min(on(t, L[1] + 0.15 * k, 0.3), off), lambda p, x=x, y=y, w=w, h=h, side=side: v4.chat(p, x, y, w, h, side)))
    if t > L[1] + 1.1:
        n = min(3, int((t - L[1] - 1.1) * 4))

        def mine(p):
            v4.chat(p, 790, 1730, 220, 110, -1, lines=0)
            for i in range(n):
                p.disc(754 + 36 * i - 10, 1720, 754 + 36 * i + 10, 1740)
        els.append(drawn(c, f"mine{n}", v, min(on(t, L[1] + 1.1, 0.3), off), mine))
    return logo_pop(stack(*els), t, L[0] + 0.6, 540, 1170, 300, off)


def shot_tony(t, v, c, te):
    off = clip01((te - t) / OFF)
    els = [tony(c, v, min(on(t, L[2], 1.4), off))]

    def group(p):
        for x, y in ((760, 470), (880, 440), (990, 490)):
            v4.person(p, x, y, 0.75)
        v4.chat(p, 820, 300, 150, 70, 1, 1, 2.6)
        v4.chat(p, 960, 280, 130, 64, -1, 1, 2.6)
    els.append(drawn(c, "group", v, min(on(t, L[3], 0.9), off), group))
    gone = L[6] + 0.4
    els.append(drawn(c, "q", v, on(t, L[4], 0.5, gone), lambda p: p.line(arc(300, 640, 50, 50, 200, 400, 30) + [(300, 720)], w=7)))
    els.append(drawn(c, "qx", v, on(t, L[4] + 1.0, 0.35, gone), lambda p: v4.scribble_out(p, 300, 680, 150, 170)))
    els.append(drawn(c, "say", v, on(t, L[5], 0.5, gone), lambda p: v4.chat(p, 260, 1000, 300, 150, 1, 3)))
    els.append(drawn(c, "sayx", v, on(t, L[5] + 1.1, 0.3, gone), lambda p: (p.line([(130, 900), (390, 1100)], w=6), p.line([(390, 900), (130, 1100)], w=6))))
    if t > L[6]:  # his bubble shrinks back into him, drawing by drawing
        s = 1 - ease((t - L[6] - 0.2) / 1.2)
        if s > 0.06:
            els.append(drawn(c, f"back{round(s, 2)}", v, off, lambda p: v4.chat(p, 480 + 60 * (1 - s), 1130, 180 * s, 90 * s, 1, 0)))
    return stack(*els).convert("RGB")


DIVE0 = L[9] + 0.7
DIVE_LEN, ZMAX = 1.1, 5.0
CARD_END = L[10] - 0.45  # the camera starts backing away
PULL_LEN, SMALL_LEN = 1.4, 1.0
WRITE0, WRITE1 = DIVE0 + DIVE_LEN + 0.15, DIVE0 + DIVE_LEN + 1.75
DESK_C = (560.0, 1372.0)
TABLE_C = (606.0, 1572.0)
CARD_C = (540.0, 1040.0)


def ink_count(t):
    return int(INK_N * clip01((t - WRITE0) / (WRITE1 - WRITE0)))


def shot_school(t, v, c, te):
    """The schoolboy, then the camera's run up to the paper on his desk (redrawn every drawing)."""
    u = ease(clip01((t - DIVE0) / DIVE_LEN))
    z = 1 + (ZMAX - 1) * u ** 1.4
    bg_p = clip01((1 - u) / 0.45)  # the classroom rubs itself out as the paper fills the screen
    with cam(z, DESK_C, lerp2(DESK_C, CARD_C, u)):
        els = [drawn(c, "kid", v, min(on(t, L[7], 1.1), bg_p), kid_desk),
               drawn(c, "friends", v, min(on(t, L[8], 0.6), bg_p), friends),
               drawn(c, "teacher", v, min(on(t, L[8] + 0.9, 0.6), bg_p), teacher),
               drawn(c, "close", v, min(on(t, L[9], 0.6), bg_p), close)]
        q_desk = q_through_cam(Q_DESK)
    Q = [lerp2(a, b, u ** 1.2) for a, b in zip(q_desk, QC)]  # the paper rises to face us
    lines, red = card_layer(c, "card", v, Q, 0, on(t, L[7] + 0.6, 0.5))
    return colour(under(stack(*els), lines, Q), red)


def shot_card(t, v, c, te):
    lines, red = card_layer(c, "card", v, QC, ink_count(t))
    return colour(lines, red)


SH_C, SH_S = (590.0, 1300.0), 0.72
CROWD_SLOT = (520.0, 932.0)  # where his shell ends, among the others (the base of its dome)
CROWD_Z = 0.22
CROWD_T = L[18]


def shell_camera(t):
    """Back from the paper to his table, back again as he makes himself small, then far back among the others."""
    a = CARD_END
    if t < a + PULL_LEN:
        u = ease(clip01((t - a) / PULL_LEN))
        return 1 + (ZMAX - 1) * (1 - u) ** 1.4, TABLE_C, lerp2(CARD_C, TABLE_C, u), u
    if t < CROWD_T:
        u = ease(clip01((t - a - PULL_LEN) / SMALL_LEN))
        return 1 - (1 - SH_S) * u, SH_C, SH_C, 1.0
    u = ease(clip01((t - CROWD_T) / 1.3))
    return lerp(SH_S, CROWD_Z, u), lerp2(SH_C, (590.0, 1180.0), u), lerp2(SH_C, CROWD_SLOT, u), 1.0


def shell_world(t, v, c, off):
    """Tony, his report card on the table, the shell over him: through the camera."""
    z, p, q, pull = shell_camera(t)
    with cam(z, p, q):
        me = tony(c, v, min(clip01(pull / 0.5), off))
        dim = 1 - 0.4 * ease((t - L[15]) / 1.0)
        if me is not None and dim < 1:
            me = Image.eval(me, lambda x: int(x * dim))
        sh = None
        if t > L[12] - 0.25:
            ep.S4 = L[12] - 0.25
            v4.PROG[0] = off
            sh = ep.shell(v, ep.S4 + (t - ep.S4) * 2.0).resize((W, H), Image.LANCZOS)
            v4.PROG[0] = 1.0
        q_table = q_through_cam(Q_TABLE)
    Q = [lerp2(a, b, pull ** 0.7) for a, b in zip(QC, q_table)]  # the paper lands on the table
    lines, red = card_layer(c, "card", v, Q, INK_N, off)
    pic = under(stack(me), lines, Q)
    if sh is not None:
        pic = Image.composite(sh, pic, sh.point(lambda x: 255 if x > 0 else 0))
    return pic, red


def shot_shell(t, v, c, te):
    off = clip01((te - t) / OFF)
    pic, red = shell_world(t, v, c, off)
    cx, cy, rx, ry = v4.DOME
    head = (611, 1062)
    gone = CROWD_T
    els = []
    if L[11] < t < L[12] + 0.6:  # ideas flying back into his head, drawing by drawing
        def ideas(p):
            for k in range(5):
                u = ease((t - L[11] - 0.25 * k) / 1.3)
                if 0 < u < 1:
                    x0, y0 = 150 + k * 190, 560 + (k % 2) * 90
                    x, y = x0 + (head[0] - x0) * u, y0 + (head[1] - y0) * u
                    r = 34 * (1 - u) + 4
                    p.line(arc(x, y, r, r, 0, 360, 24), w=3)
                    p.line([(x, y + r), (x, y + r + 12 * (1 - u))], w=2.5)
        els.append(drawn(c, f"ideas{round(t, 3)}", v, 1, ideas))
    if L[13] < t < L[15]:  # it protects him: things thrown at it bounce off
        def darts(p):
            for ang, at in ((200, 0), (330, 0.35), (250, 0.7), (300, 1.05)):
                u = (t - L[13] - at) / 0.45
                if u <= 0:
                    continue
                a = math.radians(ang)
                ex, ey = cx + (rx + 10) * math.cos(a), cy + (ry + 10) * math.sin(a)
                sx, sy = cx + (rx + 420) * math.cos(a), cy + (ry + 420) * math.sin(a)
                if u < 1:
                    x, y = sx + (ex - sx) * u, sy + (ey - sy) * u
                else:
                    b = min(1.5, u - 1)
                    x, y = ex + 90 * b * math.cos(a), ey + 90 * b * math.sin(a) + 200 * b * b
                dx, dy = math.cos(a), math.sin(a)
                p.line([(x + dx * 70, y + dy * 70), (x, y)], w=4)
                p.line([(x + dx * 20 - dy * 14, y + dy * 20 + dx * 14), (x, y), (x + dx * 20 + dy * 14, y + dy * 20 - dx * 14)], w=4)
        els.append(drawn(c, f"darts{round(t, 3)}", v, 1, darts))

    def outside(p):
        v4.person(p, 110, 1360, 0.9)
        v4.person(p, 980, 1360, 0.9)
        v4.chat(p, 150, 1150, 130, 64, 1, 1, 2.4)
        v4.chat(p, 940, 1150, 130, 64, -1, 1, 2.4)
    els.append(drawn(c, "outside", v, on(t, L[14], 0.7, gone), outside))

    def faith(p):
        p.line([(cx, cy - ry + 120), (cx, cy - ry + 230)], w=5)
        p.line([(cx - 38, cy - ry + 155), (cx + 38, cy - ry + 155)], w=5)
        v4.glow(p, cx, cy - ry + 170, 70, 110, 40)
    els.append(drawn(c, "faith", v, on(t, L[15], 0.7, gone), faith))
    if L[16] + 0.2 < t < gone:  # questions knocking against the walls
        fade = 1 - 0.6 * ease((t - L[17]) / 1.5)

        def inside(p):
            for k in range(4):
                u = t * (0.9 + 0.2 * k) + k * 1.7
                x = cx + (rx - 110) * 0.8 * math.sin(u)
                y = cy - ry * 0.35 + 110 * math.sin(u * 1.3 + k)
                if k % 2 == 0:
                    p.line(arc(x, y - 18, 22, 22, 200, 400, 20) + [(x, y + 14)], w=4, fill=int(255 * fade))
                else:
                    v4.chat(p, x, y, 80, 46, 1, 1, 2.4)
        els.append(drawn(c, f"inside{round(t, 3)}", v, min(1.0, clip01((gone - t) / 0.3)), inside))
    for k, (x, y) in enumerate(v4.CROWD9):  # the others: shell after shell
        if k == 2:
            continue  # his own place
        at = CROWD_T + 1.1 + 0.4 * min(k, 3) if k < 4 else L[19] + 0.22 * (k - 3)
        els.append(drawn(c, f"m{k}", v, min(on(t, at, 0.45), off), lambda p, x=x, y=y: v3.mini_shell(p, x, y, 0.8)))
    return colour(stack(pic, *els), red)


def shot_rise(t, v, c, te):
    off = clip01((te - t) / OFF)
    els = [drawn(c, "rphone", v, min(on(t, L[20], 0.7), off), lambda p: v4.phone_body(p, 540, 1080, 400, 760)),
           drawn(c, "rglow", v, min(on(t, L[20] + 0.9, 0.4), off), lambda p: v4.glow(p, 540, 1080, 430, 500, 90, 1.8))]

    def feed(p):
        for k in range(3):
            y = 1000 + k * 150
            p.line([(380, y), (700, y), (700, y + 115), (380, y + 115), (380, y)], w=2.6)
            p.line(arc(420, y + 35, 18, 18, 0, 360, 16), w=2)
            p.line([(455, y + 30), (660, y + 30)], w=2)
            p.line([(400, y + 75), (680, y + 75)], w=2)
    els.append(drawn(c, "feed", v, min(on(t, L[21], 0.8), off), feed))
    for k, (x, y, kind) in enumerate(v4.FEATURES):
        def cardf(p, x=x, y=y, kind=kind):
            p.line([(x - 120, y - 150), (x + 120, y - 150), (x + 120, y + 150), (x - 120, y + 150), (x - 120, y - 150)], w=3.4)
            v3.icon(p, kind, x, y - 20) if kind != "g" else v3.icon(p, kind, x, y - 90)
        els.append(drawn(c, f"feat{k}", v, min(on(t, L[22 + k], 0.5), off), cardf))
    if t > L[25]:
        u = ease((t - L[25] - 0.5) / 1.2)

        def sent(p):
            v3.mini_shell(p, 540, 1760, 0.6)
            if u > 0:
                v4.chat(p, 540, 1640 - 170 * u, 120, 56, 1, 1, 2.4)
        els.append(drawn(c, f"sent{round(u, 2)}", v, min(on(t, L[25], 0.5), off), sent))
    return logo_pop(stack(*els), t, L[20] + 0.5, 540, 860, 320, off)


def shot_gather(t, v, c, te):
    off = clip01((te - t) / OFF)
    a = L[26]
    v4.PROG[0] = min(on(t, a, 0.6), off)
    img = v3.crowd(v, t, (t - a) / (te - a - 0.8)).resize((W, H), Image.LANCZOS) if v4.PROG[0] > 0 else Image.new("L", (W, H), 0)
    v4.PROG[0] = 1.0
    return logo_pop(img, t, a + 2.0, 540, 760, 380, off)


def shot_logo(t, v, c, te):
    base = Image.new("RGB", (W, H), 0)
    sp = v3.splash_frame(t - L[28])
    base.paste(sp, ((W - sp.width) // 2, 760 - sp.height // 2), sp)
    return base


SHOTS = [(shot_hook, 0.0, L[2]), (shot_tony, L[2], L[7]), (shot_school, L[7], DIVE0 + DIVE_LEN),
         (shot_card, DIVE0 + DIVE_LEN, CARD_END), (shot_shell, CARD_END, L[20]), (shot_rise, L[20], L[26]),
         (shot_gather, L[26], L[28]), (shot_logo, L[28], DURATION + 1)]


def picture(t, v, c):
    for fn, a, b in SHOTS:
        if a <= t < b:
            return fn(t, v, c, b)
    return shot_logo(t, v, c, DURATION + 1)


# --- the words, one at a time, hand-lettered, boiling with the drawing
WORDS = {}


def words(text, k, v):
    key = (text, k, v)
    if key in WORDS:
        return WORDS[key]
    f = v3.TEXT_FONT
    lines = v3.wrap(text)
    rng = np.random.default_rng(zlib.crc32(f"{text}{v}".encode()))
    im = Image.new("RGBA", (W, 100 * len(lines) + 40), (0, 0, 0, 0))
    n = 0
    for i, line in enumerate(lines):
        ln = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
        d = ImageDraw.Draw(ln)
        x0 = (W - f.getlength(line)) / 2
        ws = line.split(" ")
        for j, w in enumerate(ws):
            if n >= k:
                break
            x = x0 + f.getlength(" ".join(ws[:j]) + (" " if j else ""))
            fill = v3.FLAME + (255,) if w.startswith("RISE") else (255, 255, 255, 255)
            d.text((x, 15), w, font=f, fill=fill, stroke_width=7, stroke_fill=(0, 0, 0, 255))
            n += 1
        ln = ln.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC)
        im.alpha_composite(ln, (int(rng.uniform(-3, 3)), int(i * 100 + rng.uniform(-3, 3))))
    WORDS[key] = im
    return im


def frame_at(t, c):
    v = int(t * DRAWINGS) % 3
    base = picture(t, v, c).convert("RGBA")
    line = next(l for l in LINES if l["t0"] <= t < l["t1"] or l is LINES[-1])
    last = line is LINES[-1]
    start = line["t0"] + (0.9 if last else 0)
    if t >= start:
        k = 1 + int((t - start) * v3.WPS)
        base.alpha_composite(words(line["text"], k, v), (0, 1040 if last else 150))
    return base.convert("RGB")


def sound(path, until=DURATION):
    """No music: silence until his voice comes in, and the boom when the logo's letters burst out."""
    sr = 48000
    n = int(until * sr)
    y = np.zeros((n, 2))
    boom, _ = sf.read(v3.BOOM, always_2d=True)
    at = int((L[28] + 0.467) * sr)
    k = min(len(boom), n - at)
    if k > 0:
        y[at:at + k] += 0.8 * boom[:k]
    sf.write(path, y, sr)


def main(until=DURATION):
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    name = "episode1_v5.mp4" if until >= DURATION else f"episode1_v5_0-{until:g}s.mp4"
    with tempfile.TemporaryDirectory() as d:
        c, last, img = {}, None, None
        for f in range(int(min(until, DURATION) * FPS)):
            g = int(f / FPS * DRAWINGS)  # the drawing this frame shows
            if g != last:
                img = frame_at(g / DRAWINGS, c)
                last = g
                if len(c) > 400:  # keep the memory in check: still drawings are cheap to redo
                    c.clear()
            img.save(f"{d}/{f:05d}.png")
        sound(f"{d}/a.wav", min(until, DURATION))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{d}/%05d.png", "-i", f"{d}/a.wav",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(out / name)], check=True)
    print(out / name, f"{min(until, DURATION):.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--until":
        main(float(sys.argv[2]))
    elif len(sys.argv) > 1:
        c = {}
        for s in sys.argv[1:]:
            tt = int(float(s) * DRAWINGS) / DRAWINGS
            frame_at(tt, c).save(ROOT / f"still_{s}.png")
    else:
        main()
