"""Tony drawn the way his very first drawing was (draw_test.py), the style he wants, but in black on white paper:
lines put down once, freehand, never gone back over to clean them. A felt pen and no ruler, no compass: each
stroke wanders a little on its way, swells where the pen lands and thins where it lifts, runs past its ends; a
long one is sometimes done in two goes; a circle never quite closes; hatching stops near the edge, not on it;
here and there a line was drawn twice, a little beside itself. The same hand-placed drawing as draw_test.py,
made posable (his head, his eyes, his mouth, his hand), so the other pictures of the film can be drawn the same way.
Usage: python3 tools/sketch.py  -> renders/tony_sketch_hello.png (« Moi c'est Tony. »)
                                   renders/tony_sketch_phone.png (the first drawing, redrawn on white)
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter1d

import draw_test as dt
import letters
from draw_test import P, Pen, arc, bez, dense, ink, wobble

ROOT = Path(__file__).resolve().parents[1]
W, H, S = dt.W, dt.H, dt.S
OUTLINE = json.loads((ROOT / "assets/rise_logo_outline.json").read_text())
PAPER = np.array((250, 248, 243), np.float32)
INK = np.array((24, 22, 22), np.float32)
ORANGE = np.array((255, 109, 0), np.float32)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def arclen(p):
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])


def resample(p, step):
    s = arclen(p)
    if s[-1] < step:
        return p
    t = np.linspace(0, s[-1], int(s[-1] / step) + 1)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def chaikin(pts, n=2):
    """Rounds a polyline's corners (its ends stay where they are)."""
    p = np.asarray(pts, float)
    for _ in range(n):
        a, b = p[:-1], p[1:]
        p = np.vstack([p[:1], np.stack([0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b], 1).reshape(-1, 2), p[-1:]])
    return [tuple(q) for q in p]


def rot(pts, cx, cy, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def loop_pts(rng, cx, cy, rx, ry, rot_deg=0.0):
    """A circle drawn freehand: it starts anywhere, comes round a little past where it began without landing on
    it, and is a touch egg-shaped."""
    a0 = rng.uniform(0, 360)
    th = np.radians(np.linspace(a0, a0 + 360 + rng.uniform(10, 32), max(28, int((rx + ry) * 0.5))))
    u = (th - th[0]) / (2 * np.pi)
    k = 1 + rng.uniform(-0.06, 0.06) * u + rng.uniform(-0.035, 0.035) * np.sin(2 * th + rng.uniform(0, 6.3))
    x, y = rx * k * np.cos(th), ry * k * np.sin(th)
    r = math.radians(rot_deg)
    return list(zip(cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)))


def rounded(quad, r=14.0, n=5):
    """A quadrilateral with rounded corners, as one closed run of points."""
    q = [np.array(c, float) for c in quad]
    out = []
    for i in range(len(q)):
        a, b, c = q[i - 1], q[i], q[(i + 1) % len(q)]
        p0 = b + (a - b) / np.hypot(*(a - b)) * r
        p1 = b + (c - b) / np.hypot(*(c - b)) * r
        out += [tuple((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1) for t in np.linspace(0, 1, n)]
    return out


def _overshoot(pts, a, b):
    (x0, y0), (x1, y1) = pts[0], pts[1]
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    d0 = math.hypot(x0 - x1, y0 - y1) or 1.0
    d1 = math.hypot(xb - xa, yb - ya) or 1.0
    return [(x0 + (x0 - x1) / d0 * a, y0 + (y0 - y1) / d0 * a)] + pts + [(xb + (xb - xa) / d1 * b, yb + (yb - ya) / d1 * b)]


def _corners(pts, deg=50.0):
    """Cuts a polyline at its sharp turns: a hand draws a box side by side."""
    out, cur = [], [pts[0]]
    for i in range(1, len(pts) - 1):
        cur.append(pts[i])
        a, b = np.subtract(pts[i], pts[i - 1]), np.subtract(pts[i + 1], pts[i])
        c = float(a @ b) / (np.hypot(*a) * np.hypot(*b) + 1e-9)
        if math.degrees(math.acos(max(-1.0, min(1.0, c)))) > deg:
            out.append(cur)
            cur = [pts[i]]
    out.append(cur + [pts[-1]])
    return out


class Hand(Pen):
    """A felt pen held freehand. Every stroke aims at its ends and wanders between them, bows a little when it is
    long, lands a little heavy and lifts thin, may run past its ends, may be done in two goes, may be gone over a
    second time a little beside itself."""

    def wander(self, p, d):
        s = arclen(p) / S
        L = s[-1]
        if L < 2 or d <= 0:
            return p
        env = np.clip(np.sin(np.pi * s / L), 0.0, 1.0) ** 0.7  # the ends stay where they were aimed
        amp = d * min(1.0, L / 220.0) * S
        out = p.copy()
        for axis in (0, 1):
            f = sum(self.rng.normal() * np.sin(2 * np.pi * s / self.rng.uniform(90, 320) + self.rng.uniform(0, 2 * np.pi)) for _ in range(3))
            out[:, axis] += f / math.sqrt(3) * amp * env
        chord = p[-1] - p[0]
        c = float(np.hypot(*chord))
        if c > 0.6 * L * S:  # nearly straight: the arm swings it into a slight bow
            n = np.array([-chord[1], chord[0]]) / c
            bow = float(np.clip(self.rng.normal(0, 0.006 * L), -10, 10)) * S
            out += n[None, :] * (bow * np.sin(np.pi * s / L))[:, None]
        return out

    def stroke(self, p, w, fill):
        """Inks a stroke: its width breathes along it, swells as the pen lands, thins out as it lifts."""
        p = resample(p, 3.0)
        if len(p) < 2:
            return
        s = arclen(p)
        L = s[-1]
        r = w * S * ink() / 2 * (0.8 + 0.4 * gaussian_filter1d(self.rng.random(len(p)), 4))
        r = r * (0.5 + 0.5 * smoothstep(s / (12 * S))) * (0.22 + 0.78 * smoothstep((L - s) / (24 * S)))
        m = 60 * S
        inside = (p[:, 0] > -m) & (p[:, 0] < W * S + m) & (p[:, 1] > -m) & (p[:, 1] < H * S + m)
        t = np.diff(p, axis=0)
        n = np.hypot(t[:, 0], t[:, 1]) + 1e-9
        nx, ny = -t[:, 1] / n, t[:, 0] / n
        a, b, ra, rb = p[:-1], p[1:], r[:-1], r[1:]
        quads = np.stack([a[:, 0] + nx * ra, a[:, 1] + ny * ra, b[:, 0] + nx * rb, b[:, 1] + ny * rb,
                          b[:, 0] - nx * rb, b[:, 1] - ny * rb, a[:, 0] - nx * ra, a[:, 1] - ny * ra], 1)
        for q in quads[inside[:-1] | inside[1:]].tolist():
            self.d.polygon(q, fill=fill)
        j = np.r_[np.arange(0, len(p), 2), len(p) - 1]
        j = j[inside[j]]
        for x0, y0, x1, y1 in np.stack([p[j, 0] - r[j], p[j, 1] - r[j], p[j, 0] + r[j], p[j, 1] + r[j]], 1).tolist():
            self.d.ellipse([x0, y0, x1, y1], fill=fill)

    def line(self, pts, w=4, amp=1.6, fill=255, again=0.25, over=6.0, drift=1.0, corners=False, breaks=True):
        pts = [(float(x), float(y)) for x, y in pts]
        if len(pts) < 2:
            return
        if corners:
            for piece in _corners(pts):
                self.line(piece, w, amp, fill, again, over, drift, False, breaks)
            return
        if over:
            pts = _overshoot(pts, self.rng.uniform(0, over), self.rng.uniform(0, over))
        p = dense(pts)
        parts = [p]
        if breaks and arclen(p)[-1] / S > 260 and self.rng.random() < 0.4:  # in two goes: lifted, set down just beside
            i = int(len(p) * self.rng.uniform(0.35, 0.65))
            parts = [p[:i + 1], p[max(0, i - int(self.rng.integers(0, 3))):] + self.rng.normal(0, 1.4, 2) * S]
        for q in parts:
            self.stroke(wobble(self.wander(q, 2.6 * drift), self.rng, amp), w, fill)
        if again and len(p) > 3 and self.rng.random() < again:  # gone over again, in part, a little beside
            n = len(p)
            i0 = int(self.rng.integers(0, max(1, n // 3)))
            i1 = int(self.rng.integers(max(i0 + 2, 2 * n // 3), n + 1))
            q = p[i0:i1] + self.rng.normal(0, 2.0, 2) * S
            self.stroke(wobble(self.wander(q, 2.6 * drift), self.rng, amp * 1.3), w * 0.55, fill)

    def hatch(self, mask_pts, angle, gap, w=2.2, jitter=0.35, length=None, amp=0.7):
        """Hatching put down quickly: strokes not quite parallel nor evenly spaced, each stopping near the shape's
        edge, mostly a little short of it, now and then a little over."""
        m = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(m).polygon([tuple(q) for q in P(mask_pts)], fill=255)
        mask = np.asarray(m) > 0
        xs, ys = [q[0] for q in mask_pts], [q[1] for q in mask_pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        R = max(max(xs) - min(xs), max(ys) - min(ys))
        ts = np.arange(-R, R + 2, 2.0)
        ux, uy = -math.sin(math.radians(angle)), math.cos(math.radians(angle))
        k = -R + gap * self.rng.uniform(0, 1)
        while k < R:
            a = math.radians(angle + self.rng.normal(0, 2.5))
            dx, dy = math.cos(a), math.sin(a)
            ox, oy = cx + ux * k, cy + uy * k
            sp = P(np.stack([ox + dx * ts, oy + dy * ts], 1)).astype(int)
            ok = (sp[:, 0] >= 0) & (sp[:, 0] < mask.shape[1]) & (sp[:, 1] >= 0) & (sp[:, 1] < mask.shape[0])
            ins = np.zeros(len(ts), bool)
            ins[ok] = mask[sp[ok, 1], sp[ok, 0]]
            e = np.diff(np.r_[0, ins.astype(int), 0])
            for i0, i1 in zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1) - 1):
                t0, t1 = ts[i0], ts[i1]
                run = t1 - t0
                if run < 5:
                    continue
                if length:  # dashes here and there along it
                    spans = []
                    for _ in range(max(1, int(round(run / 520)))):
                        ld = min(run, length * self.rng.uniform(0.7, 1.3))
                        u0 = self.rng.uniform(t0, t1 - ld)
                        spans.append((u0, u0 + ld))
                else:
                    spans = [(t0 + run * self.rng.uniform(-0.03, 0.12), t1 - run * self.rng.uniform(-0.03, 0.12))]
                for u0, u1 in spans:
                    self.line([(ox + dx * u0, oy + dy * u0), (ox + dx * u1, oy + dy * u1)], w=w * (1 + self.rng.uniform(-jitter, jitter)),
                              amp=amp, again=0.0, over=0.0, drift=0.35, breaks=False)
            k += gap * self.rng.uniform(0.75, 1.25)


# --- the first drawing's pieces, as they were placed
def table(pen):
    pen.line([(-10, 1470), (1090, 1462)], w=5)
    for x in range(40, 1100, 170):
        pen.line([(x, 1475), ((x - 540) * 1.6 + 540, 1920)], w=1.8, amp=1.2, again=0.1)
    pen.hatch([(0, 1478), (1080, 1470), (1080, 1920), (0, 1920)], 8, 26, w=1.3, length=70)


def body(pen):
    """A round-neck tee: its folds, a shadow down one side, the ribbed collar; the neck."""
    outline = [(250, 1470), (300, 1330), (420, 1255), (520, 1232), (720, 1236), (840, 1290), (930, 1400), (960, 1470)]
    pen.line(chaikin(outline, 2), w=5, again=0.3)
    for x0, x1 in ((380, 360), (470, 455), (800, 830), (880, 905)):
        pen.line([(x0, 1300), ((x0 + x1) / 2 + 6, 1390), (x1, 1465)], w=2.4, amp=2.2)
    pen.hatch([(300, 1340), (420, 1262), (470, 1300), (430, 1470), (260, 1470)], 62, 16, w=1.5)
    collar_o = arc(625, 1215, 125, 48, 10, 170, 40)
    collar_i = arc(625, 1200, 100, 34, 170, 10, 40)
    pen.hatch(collar_o + collar_i, 95, 10, w=1.8)
    pen.line(collar_o, w=3.5)
    pen.line([(555, 1120), (562, 1205)], w=4)
    pen.line([(690, 1125), (685, 1205)], w=4)
    pen.hatch([(560, 1150), (690, 1150), (686, 1200), (564, 1200)], 70, 15, w=1.3)


def cap(pen, rng, Hd):
    """His cap, worn backwards: its crown with a little shade down one side, its seams up to the button; over
    his forehead the opening above its strap, a little hair in it; the end of its peak, behind him, on our right."""
    tab = [(168, -86), (204, -86), (222, -77), (218, -64), (196, -60), (172, -62)]
    pen.poly(Hd(tab), fill=0)
    pen.line(Hd(chaikin(tab + tab[:1], 2)), w=3.0, over=2.0)
    dome = arc(2, -70, 178, 196, 176, 364, 60)
    edge = bez((-176, -56), (-96, -114), (96, -114), (180, -56), 30)
    pen.poly(Hd(dome + edge[::-1]), fill=0)
    pen.hatch(Hd([(-176, -62), (-180, -132), (-152, -204), (-100, -246), (-74, -160), (-102, -104)]), 60, 13, w=1.3)
    pen.line(Hd(dome), w=4.6, again=0.35)
    pen.line(Hd(edge), w=4.2, again=0.3)
    pen.line(Hd([(x, y - 13) for x, y in edge[5:-5]]), w=1.4, amp=1.0, again=0.0)  # its stitching
    for x0 in (-122, 122):  # the seams, to the button
        y0 = min(edge, key=lambda q: abs(q[0] - x0))[1] - 14
        pen.line(Hd(bez((x0, y0), (x0 * 1.08, -160), (x0 * 0.66, -232), (0, -262), 16)), w=2.0)
    pen.line(Hd(bez((0, -150), (2, -190), (1, -228), (0, -260), 12)), w=2.0)
    pen.line(Hd(loop_pts(rng, 0, -264, 10, 8)), w=2.6, over=0, breaks=False, drift=0.3)
    opening = arc(0, -103, 40, 46, 180, 360, 24)
    pen.poly(Hd(opening), fill=0)
    for k in range(8):  # his hair, pushed up in it
        x = -28 + 8 * k + rng.uniform(-2, 2)
        pen.line(Hd([(x, -116), (x + rng.uniform(-3, 5), -128 - rng.uniform(0, 14) + abs(x) * 0.4)]), w=1.6, again=0.0, over=0.0, drift=0.0, breaks=False)
    pen.line(Hd(opening), w=3.0, over=3.0)
    pen.line(Hd([(-44, -116), (44, -115)]), w=2.2, over=4.0)  # the strap, its holes
    for k in range(4):
        pen.poly(Hd(arc(-24 + 16 * k, -108, 3.4, 3.0, 0, 360, 8)))
    for side in (-1, 1):  # his hair at the temples, below it
        for k in range(7):
            x = side * (158 - 3.6 * k)
            pen.line(Hd([(x, -58 + 2 * k), (x + side * 1.5, -30 + 3 * k)]), w=1.5, amp=0.4, again=0.0, over=0.0, drift=0.0, breaks=False)


def head(pen, rng, hx=620.0, hy=960.0, tilt=9.0, look=(0.0, 1.0), lids=12.0, smile=0.0, brow=0.0, ears=(True, False)):
    """His head as the first drawing has it, in his cap: look is where his eyes go (-1..1), lids how open they are
    (12 tired, 16 open), smile 0 flat to 1 a small smile, brow up when > 0. Every point turns with the tilt."""
    def R(pts):  # the features were placed for a 9-degree tilt
        return rot(pts, hx, hy, tilt - 9.0)

    def Hd(pts):  # given from the middle of his head, turned with it
        return rot([(hx + x, hy + y) for x, y in pts], hx, hy, tilt)
    pen.line(arc(hx, hy, 165, 190, 14, 174, 70, tilt), w=5, again=0.35)  # the jaw, the cheeks
    pen.line(arc(hx, hy, 165, 190, 170, 206, 12, tilt), w=4)  # his left temple
    if ears[1]:
        pen.line(arc(hx, hy, 165, 190, -26, 18, 12, tilt), w=4)  # his right temple
    for k in range(120):  # his beard, kept short
        a = math.radians(rng.uniform(28, 152) + tilt)
        rr = rng.uniform(0.8, 0.98)
        x, y = hx + 160 * rr * math.cos(a), hy + 186 * rr * math.sin(a)
        if y < hy + 100:
            continue
        pen.line([(x, y), (x + rng.uniform(-3, 3), y + rng.uniform(8, 14))], w=1.15, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)
    for x, y in R(bez((hx - 56, hy + 72), (hx - 26, hy + 60), (hx + 26, hy + 62), (hx + 58, hy + 78), 20)):  # a few over his lip
        x, y = x + rng.uniform(-4, 4), y + rng.uniform(-5, 5)
        pen.line([(x, y), (x + rng.uniform(-2, 2), y + rng.uniform(6, 10))], w=1.2, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)
    sm = smile
    pen.line(R(bez((hx - 40, hy + 108 - 6 * sm), (hx - 10, hy + 100 + 10 * sm), (hx + 20, hy + 102 + 10 * sm), (hx + 48, hy + 112 - 8 * sm))), w=3.5)
    pen.line(R(bez((hx - 26, hy + 126 + 3 * sm), (hx, hy + 132 + 4 * sm), (hx + 22, hy + 130 + 4 * sm), (hx + 36, hy + 125 + 3 * sm))), w=2.0)
    if sm > 0.3:  # the corners of the smile
        pen.line(R(bez((hx - 45, hy + 94), (hx - 52, hy + 98), (hx - 53, hy + 106), (hx - 47, hy + 111))), w=1.8, over=0.0, again=0.0)
        pen.line(R(bez((hx + 53, hy + 98), (hx + 60, hy + 102), (hx + 61, hy + 110), (hx + 55, hy + 115))), w=1.8, over=0.0, again=0.0)
    pen.line(R(bez((hx + 2, hy - 20), (hx - 6, hy + 10), (hx - 22, hy + 30), (hx - 8, hy + 40))), w=3)  # the nose
    pen.line(R(bez((hx - 8, hy + 40), (hx + 8, hy + 46), (hx + 26, hy + 40), (hx + 30, hy + 30))), w=3)
    gx, gy = look
    for ex, ey in ((hx - 72, hy - 30), (hx + 60, hy - 22)):
        pen.line(R(bez((ex - 30, ey), (ex - 12, ey - lids), (ex + 14, ey - lids), (ex + 32, ey + 2))), w=4.2, again=0.2)  # the lid
        pen.line(R(bez((ex - 24, ey + 8), (ex - 8, ey + 15), (ex + 12, ey + 15), (ex + 26, ey + 8))), w=1.8)
        (px, py), = R([(ex + 9 * gx, ey + 3 + 4 * gy)])
        pen.poly(arc(px, py, 9.5, 8.5, 0, 360, 14))  # the pupil, and its glint
        pen.disc(px - 6.5, py - 6.0, px - 1.5, py - 1.0, fill=0)
        b = 6 * brow
        pen.line(R(bez((ex - 34, ey - 36 - b), (ex - 12, ey - 46 - b), (ex + 12, ey - 46 - b), (ex + 36, ey - 38 - b))), w=4.6, again=0.3)  # the brow
    for gx_, gy_ in ((hx - 70, hy - 24), (hx + 62, hy - 16)):  # the glasses
        pen.line(R(loop_pts(rng, gx_, gy_, 58, 52)), w=2.6, amp=0.7, again=0.35, over=0.0, drift=0.6, breaks=False)
    pen.line(R(bez((hx - 14, hy - 34), (hx - 6, hy - 44), (hx + 2, hy - 44), (hx + 6, hy - 30))), w=2.4)
    pen.line(R([(hx - 128, hy - 30), (hx - 164, hy - 40)]), w=2.4)
    if ears[0]:
        pen.line(R(arc(hx - 168, hy - 2, 16, 34, 100, 280, 20)), w=3.5)
        pen.line(R(bez((hx - 166, hy - 18), (hx - 176, hy - 12), (hx - 176, hy + 8), (hx - 168, hy + 14))), w=1.6, over=0.0, again=0.0)
    if ears[1]:
        pen.line(R([(hx + 124, hy - 16), (hx + 160, hy - 22)]), w=2.4)
        pen.line(R(arc(hx + 168, hy + 4, 16, 34, -80, 100, 20)), w=3.5)
        pen.line(R(bez((hx + 166, hy - 12), (hx + 176, hy - 6), (hx + 176, hy + 14), (hx + 168, hy + 20))), w=1.6, over=0.0, again=0.0)
    cap(pen, rng, Hd)


def wave(pen):
    """His elbow on the table, his forearm up, his open hand beside his face: a small hello."""
    fore_l = [(842, 1465), (866, 1310), (878, 1176)]
    fore_r = [(924, 1465), (940, 1310), (946, 1172)]
    pen.poly(fore_l + fore_r[::-1], fill=0)
    hand = chaikin([(876, 1176), (866, 1080), (860, 1062), (828, 1030), (812, 1004), (828, 992), (868, 1026), (870, 1016), (866, 926), (878, 912),
                    (893, 920), (896, 1004), (900, 1000), (903, 900), (916, 890), (930, 899), (929, 998), (934, 1004), (941, 918), (953, 911),
                    (965, 920), (959, 1009), (963, 1020), (973, 962), (984, 956), (991, 966), (979, 1034), (981, 1082), (950, 1176)], 2)
    pen.poly(hand, fill=0)
    pen.line(hand, w=4.6, again=0.3)
    pen.line(fore_l, w=5)
    pen.line(fore_r, w=5)
    pen.line(bez((880, 1068), (905, 1052), (935, 1056), (962, 1072)), w=2.0)  # the palm's lines
    pen.line(bez((878, 1110), (900, 1098), (926, 1100), (944, 1112)), w=1.7)
    pen.hatch([(912, 1310), (940, 1310), (946, 1180), (918, 1180)], 75, 12, w=1.3)  # the shadow side of his arm
    pen.hatch([(900, 1360), (936, 1350), (922, 1460), (890, 1460)], 75, 12, w=1.3)
    pen.line(bez((878, 1210), (900, 1222), (926, 1220), (946, 1208)), w=2.0)  # the wrist
    for x0, y0 in ((1012, 930), (1026, 1000)):  # it moves: two small strokes beside it
        pen.line(bez((x0, y0), (x0 + 16, y0 + 18), (x0 + 16, y0 + 40), (x0 + 4, y0 + 58)), w=2.6, again=0.0)


def cheek_hand(pen):
    """The first drawing's hand, holding his head: its fingers up against his temple, the thumb under his
    cheekbone, the forearm down to the table."""
    tips = [(756, 916, 15, 14), (785, 891, 15, 15), (814, 895, 14, 14), (841, 921, 13, 12)]  # each finger's end: x, y, half width, round
    hand = [(762, 1160), (748, 1080), (740, 1000), (741, 940)]
    for k, (x, y, hw, r) in enumerate(tips):
        hand += arc(x, y, hw, r, 180, 360, 9)
        if k < len(tips) - 1:  # down between this finger and the next
            nx = tips[k + 1][0]
            hand.append(((x + nx) / 2, max(y, tips[k + 1][1]) + 18))
    hand += [(856, 950), (858, 1000), (855, 1080), (850, 1160)]
    arm = [(762, 1160), (790, 1300), (812, 1465), (912, 1465), (888, 1300), (850, 1160)]
    pen.poly(arm, fill=0)
    pen.poly(hand, fill=0)
    pen.line(hand, w=4.8, again=0.35)
    pen.line([(762, 1160), (790, 1300), (812, 1465)], w=5)
    pen.line([(850, 1160), (888, 1300), (912, 1465)], w=5)
    for k in range(len(tips) - 1):  # the fingers, side by side, down to the knuckles
        x = (tips[k][0] + tips[k + 1][0]) / 2
        y = max(tips[k][1], tips[k + 1][1]) + 18
        pen.line(bez((x, y), (x - 1, y + 30), (x + 1, y + 55), (x + 3, y + 82 - 6 * k)), w=2.2, again=0.0)
    for x, y in ((770, 1002), (797, 990), (824, 996)):  # the knuckles
        pen.line(bez((x - 9, y + 2), (x - 4, y - 4), (x + 4, y - 4), (x + 9, y + 2)), w=1.6, over=2.0, again=0.0)
    pen.line(bez((748, 1080), (735, 1060), (728, 1030), (740, 1005)), w=3.2)  # the thumb, under the cheekbone
    pen.hatch([(806, 1010), (852, 1004), (852, 1150), (808, 1150)], 80, 13, w=1.3)
    pen.hatch([(860, 1200), (890, 1300), (908, 1460), (870, 1460), (845, 1300)], 75, 12, w=1.3)
    pen.line(bez((775, 1215), (800, 1230), (830, 1228), (855, 1215)), w=2.0)  # the wrist


def phone_on_table(pen, orange, rays=34):
    """His phone on the table, lit: RISE's flame on it, coloured in orange; its light, strokes all round it."""
    rng = pen.rng
    ph = rounded([(170, 1530), (390, 1500), (420, 1610), (195, 1645)], 16)
    pen.poly(ph, fill=0)
    pen.line(ph + ph[:4], w=4, over=0.0, breaks=False, again=0.3)
    scr = rounded([(190, 1540), (378, 1514), (402, 1598), (211, 1627)], 6, 3)
    pen.line(scr + scr[:2], w=1.8, over=0.0, breaks=False, again=0.0)

    def on_screen(u, v):  # the screen's quad: u across, v down (0..1)
        q = [(190, 1540), (378, 1514), (402, 1598), (211, 1627)]
        a = (q[0][0] + (q[1][0] - q[0][0]) * u, q[0][1] + (q[1][1] - q[0][1]) * u)
        b = (q[3][0] + (q[2][0] - q[3][0]) * u, q[3][1] + (q[2][1] - q[3][1]) * u)
        return (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v)
    flame = OUTLINE["flame"][0]
    xs, ys = [q[0] for q in flame], [q[1] for q in flame]
    fx, fy, fw, fh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    pts = [on_screen(0.5 + ((x - fx) / fh - fw / fh / 2) * 0.32, 0.18 + (y - fy) / fh * 0.64) for x, y in flame[::3]]
    od = ImageDraw.Draw(orange)  # coloured in quickly, not quite inside its line
    od.polygon([tuple(q) for q in P([(x + 3, y - 2) for x, y in pts])], fill=255)
    pen.line(pts + pts[:2], w=2.0, amp=0.5, over=0.0, breaks=False, again=0.0, drift=0.3)
    for a in np.linspace(-172, 8, rays):  # the light, strokes all round it
        ra = math.radians(a + rng.uniform(-2.5, 2.5))
        r0, r1 = 150 + rng.uniform(0, 12), 150 + 190 * rng.uniform(0.45, 1.0)
        pen.line([(295 + r0 * math.cos(ra), 1575 + r0 * 0.55 * math.sin(ra)), (295 + r1 * math.cos(ra), 1575 + r1 * 0.55 * math.sin(ra))], w=1.4, amp=0.5,
                 again=0.0, over=0.0, drift=0.3, breaks=False)


def bubble(pen, cx, cy, r, symbol):
    """A thought bubble drawn freehand: a ring that does not quite close, short strokes round its inside, a sign in it."""
    rng = pen.rng
    pen.line(loop_pts(rng, cx, cy, r, r * 0.96), w=3.4, over=0.0, breaks=False, drift=0.6, again=0.3)
    for a in np.linspace(0, 360, int(r * 0.5), endpoint=False):
        ra = math.radians(a + rng.uniform(-3, 3))
        r0 = r * rng.uniform(0.64, 0.76)
        pen.line([(cx + r0 * math.cos(ra), cy + r0 * math.sin(ra)), (cx + r * 0.88 * math.cos(ra), cy + r * 0.88 * math.sin(ra))], w=1.3, amp=0.4,
                 again=0.0, over=0.0, drift=0.2, breaks=False)
    s = r * 0.32
    if symbol == "?":
        pen.line(arc(cx, cy - s * 0.6, s * 0.7, s * 0.7, 200, 400, 30) + [(cx, cy + s * 0.5)], w=5, again=0.0)
        pen.poly(arc(cx, cy + s * 0.95, 5.5, 5, 0, 360, 10))
    elif symbol == "chat":
        pen.line([(cx - s, cy - s * 0.7), (cx + s, cy - s * 0.7), (cx + s, cy + s * 0.4), (cx - s * 0.2, cy + s * 0.4),
                  (cx - s * 0.7, cy + s), (cx - s * 0.5, cy + s * 0.4), (cx - s, cy + s * 0.4), (cx - s, cy - s * 0.7)], w=4, corners=True, over=4.0)
    elif symbol == "cross":
        pen.line([(cx, cy - s * 1.1), (cx, cy + s * 1.1)], w=5)
        pen.line([(cx - s * 0.65, cy - s * 0.4), (cx + s * 0.65, cy - s * 0.4)], w=5)


def name_tag(pen, p=1.0):
    """« Tony », written by hand, and an arrow down to him."""
    st, _ = letters.layout("Tony", "scripts", 110, 0.12, hand=1.0, seed=5)
    part, _ = letters.written([[(150 + x, 560 + y) for x, y in s_] for s_ in st], p)
    for s_ in part:
        if len(s_) > 1:
            pen.line(s_, w=4.6, amp=1.0, again=0.25, over=2.0, drift=0.5, breaks=False)
    pen.line(bez((300, 610), (330, 680), (360, 720), (410, 760), 20), w=4.0)
    pen.line([(372, 768), (410, 760), (400, 722)], w=4.0, over=3.0, corners=True)


def finish(img, orange, variant):
    """Onto the paper: the felt pen skips a little on its grain; the orange goes under the ink."""
    def rough(im):
        a = np.asarray(im, np.float32)
        noise = np.random.default_rng(7 + variant).random(a.shape)
        a[noise < 0.08] *= 0.35
        return np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)).resize((W, H), Image.LANCZOS), np.float32)[..., None] / 255
    k, o = rough(img), rough(orange) * 0.92
    rgb = PAPER * (1 - o) + ORANGE * o
    rgb = rgb * (1 - k) + INK * k
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def layers(variant):
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    return img, orange, Hand(img, np.random.default_rng(100 + variant))


def hello(variant=0):
    """« Moi c'est Tony. »: at his table, he looks at us and says hello, a little shy."""
    img, orange, pen = layers(variant)
    table(pen)
    body(pen)
    head(pen, pen.rng, hx=612.0, hy=948.0, tilt=3.0, look=(0.0, -0.1), lids=15.0, smile=0.8, brow=0.35, ears=(True, True))
    wave(pen)
    phone_on_table(pen, orange)
    name_tag(pen)
    return finish(img, orange, variant)


def phone(variant=0):
    """The first drawing, redrawn on white: his head in his hand, his phone lit on the table, his thoughts over him."""
    img, orange, pen = layers(variant)
    table(pen)
    body(pen)
    head(pen, pen.rng)
    cheek_hand(pen)
    phone_on_table(pen, orange, rays=40)
    for bx, by, r, sym in ((250, 470, 120, "?"), (420, 330, 95, "chat"), (165, 720, 82, "cross"), (352, 640, 50, None), (408, 724, 24, None),
                           (440, 776, 13, None)):
        bubble(pen, bx, by, r, sym)
    return finish(img, orange, variant)


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    for name, fn in (("tony_sketch_hello", hello), ("tony_sketch_phone", phone)):
        fn(0).save(out / f"{name}.png")
        print(out / f"{name}.png")


if __name__ == "__main__":
    main()
