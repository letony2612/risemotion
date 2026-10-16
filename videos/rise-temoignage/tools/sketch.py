"""Tony's very first drawing (draw_test.py), the one he wants, redrawn in black on white paper and kept as it
was: at his table, his phone lit in front of him, the thought bubbles over him, his hair slicked back, his round
glasses, tired eyes looking down, his beard; the same table, the same folds, the same hatching. Only his hand is
gone (no hands in this film), so his head no longer rests on it.
Drawn the way that drawing was, freehand, never gone back over to clean it: a felt pen and no ruler, no compass;
each stroke wanders a little on its way, swells where the pen lands and thins where it lifts, runs past its ends;
a long one is sometimes done in two goes; a circle never quite closes; hatching stops near the edge, not on it;
here and there a line was drawn twice, a little beside itself.
Usage: python3 tools/sketch.py  -> renders/tony_sketch.png
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter1d

import draw_test as dt
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
        p = resample(dense(pts), 5.0 * S)  # evenly spaced, so the tremor is the same however the points were given
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


# --- the first drawing's pieces, where it put them
def table(pen):
    """The table: its edge, the boards running towards us, the grain of the wood."""
    pen.line([(-10, 1470), (1090, 1462)], w=5)
    for x in range(40, 1100, 170):
        pen.line([(x, 1475), ((x - 540) * 1.6 + 540, 1920)], w=1.8, amp=1.2, again=0.1)
    pen.hatch([(0, 1478), (1080, 1470), (1080, 1920), (0, 1920)], 8, 26, w=1.3, length=70)


def body(pen):
    """A round-neck tee: its folds, the hatching down one shoulder, the ribbed collar; the neck."""
    outline = [(250, 1470), (300, 1330), (420, 1255), (520, 1232), (720, 1236), (840, 1290), (930, 1400), (960, 1470)]
    pen.line(chaikin(outline, 2), w=5, again=0.3)
    for x0, x1 in ((380, 360), (470, 455), (800, 830), (880, 905)):
        pen.line([(x0, 1300), ((x0 + x1) / 2 + 6, 1390), (x1, 1465)], w=2.4, amp=2.2)
    pen.hatch([(300, 1340), (420, 1262), (470, 1300), (430, 1470), (260, 1470)], 62, 16, w=1.5)
    collar_o = arc(625, 1215, 125, 48, 10, 170, 40)
    collar_i = arc(625, 1200, 100, 34, 170, 10, 40)
    pen.hatch(collar_o + collar_i, 95, 9, w=2.0)
    pen.line(collar_o, w=3.5)
    pen.line([(555, 1120), (562, 1205)], w=4)
    pen.line([(690, 1125), (685, 1205)], w=4)
    pen.hatch([(560, 1150), (690, 1150), (686, 1200), (564, 1200)], 70, 14, w=1.4)


def head(pen, rng, hx=620.0, hy=960.0, tilt=9.0):
    """His head as the first drawing has it: round jaw and cheeks, the beard, the flat mouth, the nose, tired eyes
    looking down at his phone under heavy brows, his round glasses, both ears, his hair slicked back. The first
    drawing placed his features for its 9-degree tilt: they turn with any other."""
    def R(pts):
        return rot(pts, hx, hy, tilt - 9.0)
    pen.line(arc(hx, hy, 165, 190, 15, 175, 70, tilt), w=5, again=0.35)  # round jaw, cheeks
    pen.line(arc(hx, hy, 165, 190, 175, 205, 12, tilt), w=4)  # his temples
    pen.line(arc(hx, hy, 165, 190, -25, 15, 12, tilt), w=4)
    for k in range(170):  # the beard: short strokes over the chin and the jaw
        a = math.radians(rng.uniform(25, 155) + tilt)
        rr = rng.uniform(0.78, 0.99)
        x, y = hx + 160 * rr * math.cos(a), hy + 186 * rr * math.sin(a)
        if y < hy + 95:
            continue
        pen.line([(x, y), (x + rng.uniform(-4, 4), y + rng.uniform(10, 20))], w=1.7, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)
    mo = R(bez((hx - 70, hy + 70), (hx - 30, hy + 52), (hx + 30, hy + 55), (hx + 72, hy + 78), 101))
    for t in rng.uniform(0, 1, 70):  # the moustache: the same strokes, packed where the first drawing had its line
        x, y = mo[int(t * 100)]
        x, y = x + rng.uniform(-3, 3), y + rng.uniform(-6, 4)
        pen.line([(x, y), (x + rng.uniform(-2, 2) + (x - hx) * 0.05, y + rng.uniform(8, 13))], w=1.7, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)
    pen.line(R(bez((hx - 40, hy + 108), (hx - 10, hy + 100), (hx + 20, hy + 102), (hx + 48, hy + 112))), w=3.5)  # mouth, flat
    pen.line(R(bez((hx - 30, hy + 125), (hx, hy + 132), (hx + 25, hy + 130), (hx + 40, hy + 124))), w=2.2)  # lower lip
    pen.line(R(bez((hx + 2, hy - 20), (hx - 6, hy + 10), (hx - 22, hy + 30), (hx - 8, hy + 40))), w=3)  # the nose
    pen.line(R(bez((hx - 8, hy + 40), (hx + 8, hy + 46), (hx + 26, hy + 40), (hx + 30, hy + 30))), w=3)
    for ex, ey in ((hx - 72, hy - 30), (hx + 60, hy - 22)):  # the eyes: tired, half shut, looking down at the phone
        pen.line(R(bez((ex - 30, ey), (ex - 12, ey - 12), (ex + 14, ey - 12), (ex + 32, ey + 2))), w=4.5, again=0.25)  # heavy lid
        pen.line(R(bez((ex - 26, ey + 6), (ex - 8, ey + 14), (ex + 12, ey + 14), (ex + 28, ey + 6))), w=2)
        (px, py), = R([(ex, ey + 5)])
        pen.poly(arc(px, py, 9, 7.5, 0, 360, 14))  # the look, down
        pen.line(R(bez((ex - 22, ey + 26), (ex - 6, ey + 33), (ex + 10, ey + 33), (ex + 24, ey + 26))), w=1.6)  # the bags
        pen.line(R(bez((ex - 34, ey - 34), (ex - 12, ey - 44), (ex + 12, ey - 44), (ex + 36, ey - 36))), w=6, again=0.3)  # brow
    for gx, gy in ((hx - 70, hy - 24), (hx + 62, hy - 16)):  # the glasses: thin round wire frames, his own
        pen.line(R(loop_pts(rng, gx, gy, 58, 52)), w=2.6, amp=0.8, again=0.35, over=0.0, drift=0.6, breaks=False)
    pen.line(R(bez((hx - 14, hy - 34), (hx - 6, hy - 44), (hx + 2, hy - 44), (hx + 6, hy - 30))), w=2.4)  # the bridge
    pen.line(R([(hx - 128, hy - 30), (hx - 162, hy - 40)]), w=2.4)  # the temple arms
    pen.line(R([(hx + 124, hy - 16), (hx + 158, hy - 22)]), w=2.4)
    pen.line(R(arc(hx - 168, hy - 2, 16, 34, 100, 280, 20)), w=3.5)  # his ears
    pen.line(R(arc(hx + 168, hy + 4, 16, 34, -80, 100, 20)), w=3.5)
    # the hair: slicked back, strand by strand, a few strands falling on his left temple
    hairline = arc(hx, hy - 30, 158, 100, 192, 338, 40, tilt)
    top = arc(hx + 6, hy - 40, 176, 215, 188, 342, 40, tilt)
    pen.poly(hairline + top[::-1], fill=0)
    pen.line(top, w=4.5, again=0.3)
    for k in range(95):
        i = int(rng.uniform(0.02, 0.98) * (len(hairline) - 1))
        x0, y0 = hairline[i]
        x1, y1 = top[min(len(top) - 1, i + rng.integers(3, 9))]
        mx, my = (x0 + x1) / 2 + rng.uniform(-10, 10), (y0 + y1) / 2 - rng.uniform(10, 30)
        pen.line(bez((x0, y0 - 2), (x0 + 4, y0 - 30), (mx, my), (x1, y1 + 4)), w=rng.uniform(1.2, 2.8), amp=0.8, again=0.0, over=3.0)
    for sx, sy in ((hx - 150, hy - 70), (hx - 138, hy - 76), (hx - 122, hy - 84)):
        pen.line(R(bez((sx, sy), (sx - 14, sy + 30), (sx - 16, sy + 60), (sx - 4, sy + 92))), w=1.6)


def phone_on_table(pen, orange):
    """His phone on the table, lit: RISE's flame on it, coloured in orange; its light, scratched out round it."""
    rng = pen.rng
    ph = rounded([(170, 1530), (390, 1500), (420, 1610), (195, 1645)], 16)
    pen.poly(ph, fill=0)
    pen.line(ph + ph[:4], w=4, over=0.0, breaks=False, again=0.3)
    q = [(190, 1540), (378, 1514), (402, 1598), (211, 1627)]
    scr = rounded(q, 6, 3)
    pen.line(scr + scr[:2], w=1.8, over=0.0, breaks=False, again=0.0)

    def on_screen(u, v):  # the screen: u across, v down (0..1)
        a = (q[0][0] + (q[1][0] - q[0][0]) * u, q[0][1] + (q[1][1] - q[0][1]) * u)
        b = (q[3][0] + (q[2][0] - q[3][0]) * u, q[3][1] + (q[2][1] - q[3][1]) * u)
        return (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v)
    flame = OUTLINE["flame"][0]
    xs, ys = [c[0] for c in flame], [c[1] for c in flame]
    fx, fy, fw, fh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    pts = [on_screen(0.5 + ((x - fx) / fh - fw / fh / 2) * 0.32, 0.18 + (y - fy) / fh * 0.64) for x, y in flame[::3]]
    ImageDraw.Draw(orange).polygon([tuple(c) for c in P([(x + 3, y - 2) for x, y in pts])], fill=255)  # coloured in quickly
    pen.line(pts + pts[:2], w=2.0, amp=0.5, over=0.0, breaks=False, again=0.0, drift=0.3)
    for a in np.linspace(-170, 10, 46):  # the light, scratched out round it
        ra = math.radians(a + rng.uniform(-2, 2))
        r0, r1 = 140, 140 + 230 * 0.9 * rng.uniform(0.5, 1.0)
        pen.line([(295 + r0 * math.cos(ra), 1575 + r0 * 0.55 * math.sin(ra)), (295 + r1 * math.cos(ra), 1575 + r1 * 0.55 * math.sin(ra))], w=1.4, amp=0.5,
                 again=0.0, over=0.0, drift=0.3, breaks=False)


def bubble(pen, cx, cy, r, symbol):
    """A thought bubble: a ring that does not quite close, short strokes all round its inside, a sign in it."""
    rng = pen.rng
    pen.line(loop_pts(rng, cx, cy, r, r * 0.97), w=3.5, over=0.0, breaks=False, drift=0.6, again=0.3)
    for a in np.linspace(0, 360, int(r * 0.75), endpoint=False):
        ra = math.radians(a + rng.uniform(-2, 2))
        r0 = r * rng.uniform(0.58, 0.72)
        pen.line([(cx + r0 * math.cos(ra), cy + r0 * math.sin(ra)), (cx + r * 0.92 * math.cos(ra), cy + r * 0.92 * math.sin(ra))], w=1.4, amp=0.4,
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


def drawing(variant=0):
    """The first drawing, on white: at his table at night, his head a little on one side, looking down at his
    phone; what he does not dare (questions, talking to people) and his faith, in the bubbles over him."""
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    pen = Hand(img, np.random.default_rng(100 + variant))
    table(pen)
    body(pen)
    head(pen, pen.rng, hx=620.0, hy=962.0, tilt=6.0)
    phone_on_table(pen, orange)
    for bx, by, r, sym in ((250, 470, 120, "?"), (420, 330, 95, "chat"), (165, 720, 82, "cross"), (360, 640, 52, None), (450, 790, 26, None),
                           (500, 850, 15, None)):
        bubble(pen, bx, by, r, sym)
    return finish(img, orange, variant)


def main():
    out = ROOT / "renders" / "tony_sketch.png"
    out.parent.mkdir(exist_ok=True)
    drawing(0).save(out)
    print(out)


if __name__ == "__main__":
    main()
