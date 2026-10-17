"""Tony's very first drawing (draw_test.py), the one he wants, redrawn in black on white paper and kept as it
was: at his table, his phone lit in front of him, the thought bubbles over him, his hair slicked back, his round
glasses, tired eyes looking down, his beard; the same table, the same folds, the same hatching. Only his hand is
gone (no hands in this film), so his head no longer rests on it; his hair can be wavy, Korean style, and his beard
can go.
Drawn the way that drawing was, freehand, never gone back over to clean it: a felt pen and no ruler, no compass;
each stroke wanders a little on its way, swells where the pen lands and thins where it lifts, runs past its ends;
a long one is sometimes done in two goes; a circle never quite closes; hatching stops near the edge, not on it;
here and there a line was drawn twice, a little beside itself.
Usage: python3 tools/sketch.py  -> renders/tony_sketch.png (the drawing Tony validated; reference/tony_valide.png),
                                   renders/scene_01.png… (the film's drawings, one per line of SCRIPT.md)
"""
import json
import math
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
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

    def stroke(self, p, w, fill, taper=1.0):
        """Inks a stroke: its width breathes along it, swells as the pen lands, thins out as it lifts."""
        p = resample(p, 3.0)
        if len(p) < 2:
            return
        s = arclen(p)
        L = s[-1]
        r = w * S * ink() / 2 * (0.8 + 0.4 * gaussian_filter1d(self.rng.random(len(p)), 4))
        if taper:  # (how far the swelling and the thinning reach: less for lettering, whose strokes are short)
            r = r * (0.5 + 0.5 * smoothstep(s / (12 * S * taper))) * (0.22 + 0.78 * smoothstep((L - s) / (24 * S * taper)))
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

    def line(self, pts, w=4, amp=1.6, fill=255, again=0.25, over=6.0, drift=1.0, corners=False, breaks=True, taper=1.0):
        pts = [(float(x), float(y)) for x, y in pts]
        if len(pts) < 2:
            return
        if corners:
            for piece in _corners(pts):
                self.line(piece, w, amp, fill, again, over, drift, False, breaks, taper)
            return
        if over:
            pts = _overshoot(pts, self.rng.uniform(0, over), self.rng.uniform(0, over))
        p = resample(dense(pts), 5.0 * S)  # evenly spaced, so the tremor is the same however the points were given
        parts = [p]
        if breaks and arclen(p)[-1] / S > 260 and self.rng.random() < 0.4:  # in two goes: lifted, set down just beside
            i = int(len(p) * self.rng.uniform(0.35, 0.65))
            parts = [p[:i + 1], p[max(0, i - int(self.rng.integers(0, 3))):] + self.rng.normal(0, 1.4, 2) * S]
        for q in parts:
            self.stroke(wobble(self.wander(q, 2.6 * drift), self.rng, amp), w, fill, taper)
        if again and len(p) > 3 and self.rng.random() < again:  # gone over again, in part, a little beside
            n = len(p)
            i0 = int(self.rng.integers(0, max(1, n // 3)))
            i1 = int(self.rng.integers(max(i0 + 2, 2 * n // 3), n + 1))
            q = p[i0:i1] + self.rng.normal(0, 2.0, 2) * S
            self.stroke(wobble(self.wander(q, 2.6 * drift), self.rng, amp * 1.3), w * 0.55, fill, taper)

    def hatch(self, mask_pts, angle, gap, w=2.2, jitter=0.35, length=None, amp=0.7):
        """Hatching put down quickly: strokes not quite parallel nor evenly spaced, each stopping near the shape's
        edge, mostly a little short of it, now and then a little over."""
        z = dt.CAM[0]  # spaced the same on the page however far the camera is
        gap, length = gap / z, (length / z if length else length)
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


def spline(pts, n=8):
    """A smooth curve through the points (Catmull-Rom)."""
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return [tuple(q) for q in out]


# --- the first drawing's pieces, where it put them
def table(pen, wide=False):
    """The table: its edge, the boards running towards us, the grain of the wood (wide: running on past the
    picture's sides, for when the camera has moved)."""
    x0, x1 = (-700, 1800) if wide else (-10, 1090)
    pen.line([(x0, 1470 - 8 * (x0 + 10) / 1100), (x1, 1470 - 8 * (x1 + 10) / 1100)], w=5)
    for x in range(40 - (850 if wide else 0), 1100 + (700 if wide else 0), 170):
        pen.line([(x, 1475), ((x - 540) * 1.6 + 540, 1920)], w=1.8, amp=1.2, again=0.1)
    pen.hatch([(x0 + 10, 1478), (x1 - 10, 1470), (x1 - 10, 1920), (x0 + 10, 1920)], 8, 26, w=1.3, length=70)


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


def head(pen, rng, hx=620.0, hy=960.0, tilt=9.0, hair="wavy", beard=True, look=(0.0, 1.0), lids=12.0, smile=0.0, worry=0.0, blink=False):
    """His head as the first drawing has it: round jaw and cheeks, the beard (or none), the flat mouth, the nose,
    tired eyes looking down at his phone under heavy brows, both ears, his hair (wavy, Korean style, or slicked back
    as in that drawing), his round glasses over it. The first drawing placed his features for its 9-degree tilt:
    they turn with any other. look: where his eyes go (-1..1 across, down; the first drawing's is down at his
    phone), lids: how far his upper lids come down (12 heavy, 14 open), smile: the corners of his mouth up (> 0) or
    down (< 0), worry: the inner ends of his brows up, blink: his eyes shut."""
    def R(pts):
        return rot(pts, hx, hy, tilt - 9.0)

    def Hd(pts):  # given from the middle of his head, turned with it
        return rot([(hx + x, hy + y) for x, y in pts], hx, hy, tilt)
    pen.line(arc(hx, hy, 165, 190, 15, 175, 70, tilt), w=5, again=0.35)  # round jaw, cheeks
    pen.line(arc(hx, hy, 165, 190, 175, 205, 12, tilt), w=4)  # his temples
    pen.line(arc(hx, hy, 165, 190, -25, 15, 12, tilt), w=4)
    if beard:
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
            pen.line([(x, y), (x + rng.uniform(-2, 2) + (x - hx) * 0.05, y + rng.uniform(8, 13))], w=1.7, amp=0.3, again=0.0, over=0.0, drift=0.0,
                     breaks=False)
    else:  # shaved: only the hollow under his lip
        pen.line(R(bez((hx - 12, hy + 156), (hx - 4, hy + 161), (hx + 8, hy + 161), (hx + 16, hy + 155))), w=1.8, over=1.0, again=0.0)
    sm = smile
    pen.line(R(bez((hx - 40, hy + 108 - 4 * sm), (hx - 10, hy + 100 + 8 * sm), (hx + 20, hy + 102 + 8 * sm), (hx + 48, hy + 112 - 6 * sm))), w=3.5)  # mouth
    pen.line(R(bez((hx - 30, hy + 125), (hx, hy + 132), (hx + 25, hy + 130), (hx + 40, hy + 124))), w=2.2)  # lower lip
    pen.line(R(bez((hx + 2, hy - 20), (hx - 6, hy + 10), (hx - 22, hy + 30), (hx - 8, hy + 40))), w=3)  # the nose
    pen.line(R(bez((hx - 8, hy + 40), (hx + 8, hy + 46), (hx + 26, hy + 40), (hx + 30, hy + 30))), w=3)
    for inner, (ex, ey) in ((1, (hx - 72, hy - 30)), (-1, (hx + 60, hy - 22))):  # the eyes: tired, half shut
        if blink:  # shut: the lid down on the lower one
            pen.line(R(bez((ex - 30, ey + 3), (ex - 12, ey + 10), (ex + 14, ey + 10), (ex + 32, ey + 5))), w=4.5, again=0.25)
        else:
            pen.line(R(bez((ex - 30, ey), (ex - 12, ey - lids), (ex + 14, ey - lids), (ex + 32, ey + 2))), w=4.5, again=0.25)  # heavy lid
            pen.line(R(bez((ex - 26, ey + 6), (ex - 8, ey + 14), (ex + 12, ey + 14), (ex + 28, ey + 6))), w=2)
            (px, py), = R([(ex + 9 * look[0], ey + 5 * look[1])])
            pen.poly(arc(px, py, 9, 7.5, 0, 360, 14))  # where he looks
        pen.line(R(bez((ex - 22, ey + 26), (ex - 6, ey + 33), (ex + 10, ey + 33), (ex + 24, ey + 26))), w=1.6)  # the bags
        wl, wr = (0.0, worry) if inner > 0 else (worry, 0.0)  # worried: the brow's inner end goes up
        pen.line(R(bez((ex - 34, ey - 34 - 9 * wl), (ex - 12, ey - 44 - 4 * wl), (ex + 12, ey - 44 - 4 * wr), (ex + 36, ey - 36 - 9 * wr))), w=6,
                 again=0.3)  # brow
    pen.line(R([(hx - 128, hy - 30), (hx - 162, hy - 40)]), w=2.4)  # the glasses' arms, going under his hair
    pen.line(R([(hx + 124, hy - 16), (hx + 158, hy - 22)]), w=2.4)
    pen.line(R(arc(hx - 168, hy - 2, 16, 34, 100, 280, 20)), w=3.5)  # his ears
    pen.line(R(arc(hx + 168, hy + 4, 16, 34, -80, 100, 20)), w=3.5)
    if hair == "wavy":
        wavy_hair(pen, rng, Hd)
    else:  # slicked back, strand by strand, a few strands falling on his left temple
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
    for gx, gy in ((hx - 70, hy - 24), (hx + 62, hy - 16)):  # the glasses: thin round wire frames, his own
        pen.line(R(loop_pts(rng, gx, gy, 58, 52)), w=2.6, amp=0.8, again=0.35, over=0.0, drift=0.6, breaks=False)
    pen.line(R(bez((hx - 14, hy - 34), (hx - 6, hy - 44), (hx + 2, hy - 44), (hx + 6, hy - 30))), w=2.4)  # the bridge

# his hair, Korean style, wavy and swept back: where it starts on his forehead and temples (left to right), and its
# outline, from the left of his face over the top to the right
HAIRLINE = [(-156, -40), (-152, -84), (-136, -118), (-104, -138), (-62, -146), (-20, -150), (22, -150), (64, -146), (104, -136), (136, -116),
            (152, -82), (158, -40)]
HAIR_SIL = [(-162, -44), (-172, -86), (-182, -132), (-184, -172), (-170, -208), (-140, -236), (-96, -260), (-44, -276), (10, -281), (64, -273),
            (112, -254), (148, -227), (172, -193), (182, -156), (178, -110), (168, -72), (160, -42)]


def wave_line(p0, p1, amp, n=40, phase=0.0):
    """From p0 to p1 in one S: out to one side, back across to the other."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1.0)
    t = np.linspace(0, 1, n)[:, None]
    return p0 + t * d + nrm * (amp * np.sin(2 * np.pi * t + phase) * (1 - np.abs(2 * t - 1) ** 3))


def wavy_hair(pen, rng, Hd):
    """His hair, Korean style: thick and wavy, swept back. From where it starts on his forehead it rises and goes
    back over his head in waves, lock by lock, every lock swinging the same way so the waves run across his head; a
    little height at the front; two loose strands fall back over his forehead; a few astray on top."""
    line = resample(np.array(spline(HAIRLINE, 10)), 4.0)
    sil = np.array(spline(HAIR_SIL, 10))
    tg = np.gradient(sil, axis=0)
    tg /= np.hypot(tg[:, 0], tg[:, 1])[:, None]
    sil = resample(sil + np.stack([tg[:, 1], -tg[:, 0]], 1) * (5 * (np.abs(np.sin(np.pi * arclen(sil) / 60)) ** 0.7 - 0.45))[:, None], 4.0)
    pen.poly(Hd([tuple(q) for q in sil] + [tuple(q) for q in line[::-1]]), fill=0)

    def at(curve, u):  # the point a fraction u of the way along a curve
        s = arclen(curve)
        return np.array([np.interp(u * s[-1], s, curve[:, 0]), np.interp(u * s[-1], s, curve[:, 1])])
    us = np.linspace(0.03, 0.97, 12)
    bounds = []
    for k, u in enumerate(us):  # the lines between the locks: up from his forehead, back over the top, in nearly the same S
        h, s = at(line, u), at(sil, 0.5 + (u - 0.5) * 0.92)
        bounds.append(wave_line(h, s, min(9.0, 0.07 * float(np.hypot(*(s - h)))), phase=0.12 * k + rng.uniform(-0.1, 0.1)))
    for a, b in zip(bounds[:-1], bounds[1:]):  # each lock's strands, swinging with it
        for f in rng.uniform(0.0, 1.0, 5):
            st = (1 - f) * a + f * b
            st = st[int(len(st) * rng.uniform(0.0, 0.12)):len(st) - int(len(st) * rng.uniform(0.0, 0.1))]
            pen.line(Hd([tuple(q) for q in st]), w=rng.uniform(1.0, 2.4), amp=0.6, again=0.0, over=1.5, drift=0.3, breaks=False)
    for b in bounds:
        pen.line(Hd([tuple(q) for q in b]), w=2.6, amp=0.7, again=0.15, over=2.0, drift=0.3, breaks=False)
    pen.line(Hd([tuple(q) for q in sil]), w=4.4, again=0.3)
    for pts, w in ((((-34, -148), (-54, -134), (-68, -112), (-60, -94)), 2.2), (((-22, -150), (-36, -138), (-46, -124), (-42, -110)), 1.5)):
        st = bez(*pts, 16)  # two strands come loose and fall back over his forehead, their ends curling round
        xb, yb = st[-1]
        pen.line(Hd(st + [(xb + 2, yb + 5), (xb + 8, yb + 6), (xb + 11, yb + 1)]), w=w, again=0.0, over=0.0, drift=0.2, breaks=False)
    for x0, y0, x1, y1 in ((-104, -257, -118, -273), (14, -280, 32, -294), (150, -222, 170, -232)):  # astray
        pen.line(Hd(bez((x0, y0), (x0 + (x1 - x0) * 0.3, y0 - 10), (x1 - 6, y1 + 4), (x1, y1), 10)), w=1.2, again=0.0, over=1.0, drift=0.0,
                 breaks=False)


def phone_on_table(pen, orange, glow=0.9, rng=None, lit=1.0):
    """His phone on the table, lit: RISE's flame on it, coloured in orange; its light, scratched out round it (glow:
    how far it reaches). rng: what is random in it, to keep it put from one drawing to the next. lit: 0 while it is
    off (its screen dark), up to 1 as its light comes on."""
    rng = rng or pen.rng
    ph = rounded([(170, 1530), (390, 1500), (420, 1610), (195, 1645)], 16)
    pen.poly(ph, fill=0)
    pen.line(ph + ph[:4], w=4, over=0.0, breaks=False, again=0.3)
    q = [(190, 1540), (378, 1514), (402, 1598), (211, 1627)]
    scr = rounded(q, 6, 3)
    pen.line(scr + scr[:2], w=1.8, over=0.0, breaks=False, again=0.0)
    if lit <= 0:  # off: the screen hatched dark
        pen.hatch(scr, 58, 8, w=1.6)
        return

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
        r0, r1 = 140, 140 + 230 * glow * lit * rng.uniform(0.5, 1.0)
        if r1 - r0 > 4:
            pen.line([(295 + r0 * math.cos(ra), 1575 + r0 * 0.55 * math.sin(ra)), (295 + r1 * math.cos(ra), 1575 + r1 * 0.55 * math.sin(ra))], w=1.4,
                     amp=0.5, again=0.0, over=0.0, drift=0.3, breaks=False)


def bubble(pen, cx, cy, r, symbol, squash=1.0, rng=None):
    """A thought bubble: a ring that does not quite close, short strokes all round its inside, a sign in it
    (squash < 1: pressed flat)."""
    rng = rng or pen.rng
    pen.line(loop_pts(rng, cx, cy, r, r * 0.97 * squash), w=3.5, over=0.0, breaks=False, drift=0.6, again=0.3)
    for a in np.linspace(0, 360, int(r * 0.75), endpoint=False):
        ra = math.radians(a + rng.uniform(-2, 2))
        r0 = r * rng.uniform(0.58, 0.72)
        pen.line([(cx + r0 * math.cos(ra), cy + r0 * squash * math.sin(ra)), (cx + r * 0.92 * math.cos(ra), cy + r * 0.92 * squash * math.sin(ra))],
                 w=1.4, amp=0.4, again=0.0, over=0.0, drift=0.2, breaks=False)
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


def speech(pen, cx, cy, rx, ry, tip, content="talk", p=1.0, rng=None):
    """A speech bubble drawn freehand, its tail pointing to who speaks; in it, 'talk' (a few lines of talk), 'dots'
    (…) or 'scribble' (a tangle: what he is afraid to say), as far as p of it. It hides what is behind it."""
    rng = rng or pen.rng
    pen.poly(arc(cx, cy, rx, ry, 0, 360, 48), fill=0)
    pen.line(loop_pts(rng, cx, cy, rx, ry), w=3.2, over=0.0, breaks=False, drift=0.6, again=0.3)
    th = math.atan2((tip[1] - cy) / ry, (tip[0] - cx) / rx)

    def on(a, k=1.0):
        return (cx + rx * k * math.cos(a), cy + ry * k * math.sin(a))
    da = min(0.32, 22.0 / max(rx, ry))
    pen.poly([on(th - da, 1.12), on(th + da, 1.12), on(th + da, 0.86), on(th - da, 0.86)], fill=0)  # opened where the tail comes out
    for s in (-1, 1):
        b = on(th + s * da)
        pen.line(bez(b, (b[0] + (tip[0] - b[0]) * 0.4, b[1] + (tip[1] - b[1]) * 0.3), (tip[0] - (tip[0] - b[0]) * 0.25, tip[1] - (tip[1] - b[1]) * 0.35),
                     tip, 14), w=3.0, over=0.0, breaks=False, again=0.0)
    if content == "talk":
        for k, f in enumerate((0.85, 1.0, 0.6)):
            y = cy + (k - 1) * ry * 0.34
            pen.line([(cx - rx * 0.5 * f, y), (cx + rx * 0.5 * f, y + rng.uniform(-2, 2))], w=2.4, again=0.0, drift=0.5)
    elif content == "dots":
        for k in (-1, 0, 1)[:int(round(3 * p))]:
            pen.poly(arc(cx + k * rx * 0.36, cy + 2, 6.5, 6.0, 0, 360, 10))
    elif content == "scribble":
        ph = rng.uniform(0, 2 * math.pi, 6)
        u = np.linspace(0, 1, 1100)
        xs = cx + rx * 0.62 * (0.45 * np.sin(2 * np.pi * 4.1 * u + ph[0]) + 0.33 * np.sin(2 * np.pi * 9.3 * u + ph[1]) + 0.22 * np.sin(2 * np.pi * 15.7 * u + ph[2]))
        ys = cy + ry * 0.58 * (0.45 * np.cos(2 * np.pi * 3.3 * u + ph[3]) + 0.33 * np.sin(2 * np.pi * 7.9 * u + ph[4]) + 0.22 * np.cos(2 * np.pi * 13.1 * u + ph[5]))
        n = int(len(u) * p)
        if n > 1:
            pen.line(list(zip(xs[:n], ys[:n])), w=2.2, amp=1.0, again=0.0, over=0.0, drift=0.4, breaks=False)


def lettering(pen, text, cx, y, size, w=3.6):
    """A line of spaced capitals written freehand (the Hershey letters, as in the captions), centred on cx, sitting
    on y."""
    gap = size * 0.12
    x = cx - (letters.width(text, "futural", size) + gap * len(text)) / 2
    for i, ch in enumerate(text):
        strokes, _ = letters.layout(ch, "futural", size, hand=0.9, seed=zlib.crc32(text.encode()) + i)
        for s in strokes:
            if len(s) > 1:
                pen.line([(x + a, y + b) for a, b in s], w=w, amp=0.4, again=0.0, over=0.0, drift=0.0, breaks=False, taper=0.2)
        x += letters.width(ch, "futural", size) + gap


ALERTS = {  # what the alert in his head says: what he was about to do, the warning (in big), its two buttons
    "prière": ("DEMANDER DE LA PRIÈRE ?", ("TU RISQUES", "DE DÉRANGER."), ("ANNULER", "DEMANDER")),
    "message": ("ENVOYER LE MESSAGE ?", ("TU RISQUES", "DE DÉRANGER."), ("ANNULER", "ENVOYER")),
}


def alert(pen, cx, cy, s=1.0, circled=0.0, rng=None, says="prière"):
    """What goes on in his head when he wants to reach out to someone, drawn as his phone's alert: a warning sign,
    what he was about to do and the warning, in big (ALERTS[says]: « Demander de la prière ? Tu risques de
    déranger. »), Annuler or Demander; circled: how far the pen has gone round « Annuler » (0..1). s: its size, as it
    comes and goes like a thought. It hides what is behind it."""
    rng = rng or pen.rng
    question, warning, buttons = ALERTS[says]
    w, h = 490 * s, 360 * s
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    card = rounded([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 36 * s, 6)
    pen.poly(card, fill=0)
    pen.line(card + card[:3], w=4, over=0.0, breaks=False, again=0.3)
    tx, ty = cx, y0 + 22 * s  # the warning sign
    pen.line([(tx, ty), (tx + 33 * s, ty + 56 * s), (tx - 33 * s, ty + 56 * s), (tx, ty)], w=3.6, corners=True, over=3.0, again=0.0)
    pen.line([(tx, ty + 21 * s), (tx + 0.5 * s, ty + 38 * s)], w=4.2, over=0.0, again=0.0, breaks=False)
    pen.poly(arc(tx, ty + 46 * s, 3.5 * s, 3.2 * s, 0, 360, 10))

    def fit(lines, size, room):  # as big as it can be, up to size, inside room
        return size * min([1.0] + [room / (letters.width(t, "futural", size) + size * 0.12 * len(t)) for t in lines])
    lettering(pen, question, cx, y0 + 118 * s, fit([question], 18 * s, 0.88 * w), 2.8)
    big = fit(warning, 36 * s, 0.86 * w)
    lettering(pen, warning[0], cx, y0 + 174 * s, big, 4.4)
    lettering(pen, warning[1], cx, y0 + 223 * s, big, 4.4)
    yl = y0 + 256 * s  # the buttons
    pen.line([(x0 + 4 * s, yl), (x1 - 4 * s, yl + 2 * s)], w=2.4, over=2.0, again=0.0, breaks=False)
    pen.line([(cx, yl + 1 * s), (cx + 1 * s, y1 - 3 * s)], w=2.4, over=1.0, again=0.0, breaks=False)
    lettering(pen, buttons[0], cx - w / 4, y0 + 320 * s, 22 * s, 3.4)
    lettering(pen, buttons[1], cx + w / 4, y0 + 320 * s, 22 * s, 3.4)
    ring = loop_pts(rng, cx - w / 4, y0 + 309 * s, 100 * s, 33 * s, -3)
    n = int(len(ring) * circled)
    if n > 1:
        pen.line(ring[:n], w=3.4, over=0.0, breaks=False, drift=0.6, again=0.0)


def person(pen, x, y, s, hair="short", look=(0.0, 0.0), mouth="smile", beard=False, tilt=0.0, rng=None):
    """Someone else, from the chest up, drawn the way Tony is (a round face, plain features), with their own hair;
    never their hands: they sit behind a table that hides the rest. (x, y): the middle of their face; s: their size
    against Tony's; look: where their eyes go; mouth: 'talk', 'smile' or 'flat'. They hide what is behind them."""
    rng = rng or pen.rng

    def L(pts):  # their own coordinates, Tony's head's size, to the page
        return rot([(x + px * s, y + py * s) for px, py in pts], x, y, tilt)
    shoulders = [(-330, 600), (-312, 420), (-210, 318), (-96, 286), (96, 286), (210, 318), (312, 420), (330, 600)]
    pen.poly(L(arc(0, -14, 166, 200, 0, 360, 40)), fill=0)
    pen.poly(L(shoulders), fill=0)
    pen.line(L(chaikin(shoulders[:4], 2)), w=4.4, again=0.25)
    pen.line(L(chaikin(shoulders[4:], 2)), w=4.4, again=0.25)
    pen.line(L([(-200, 330), (-214, 430), (-206, 560)]), w=2.0, amp=1.6)  # a fold or two
    pen.line(L([(186, 340), (204, 440), (196, 560)]), w=2.0, amp=1.6)
    pen.hatch(L(arc(0, 268, 112, 42, 10, 170, 20) + arc(0, 256, 90, 30, 170, 10, 20)), 95, 9, w=1.6)  # the collar
    pen.line(L(arc(0, 268, 112, 42, 10, 170, 24)), w=3.0)
    pen.line(L([(-62, 150), (-58, 262)]), w=3.6)  # the neck, its shade under the chin
    pen.line(L([(64, 154), (60, 262)]), w=3.6)
    pen.hatch(L([(-58, 176), (60, 176), (58, 240), (-56, 240)]), 70, 13, w=1.2)
    pen.line(L(arc(0, 0, 148, 172, 12, 168, 50)), w=4.4, again=0.3)  # the face
    for sx in (-1, 1):
        pen.line(L(arc(sx * 152, 4, 14, 30, -80 if sx > 0 else 100, 100 if sx > 0 else 280, 14)), w=3.0)  # ears
    if beard:
        for k in range(110):
            a = math.radians(rng.uniform(25, 155))
            rr = rng.uniform(0.78, 0.99)
            bx, by = 144 * rr * math.cos(a), 168 * rr * math.sin(a)
            if by > 88:
                pen.line(L([(bx, by), (bx + rng.uniform(-3, 3), by + rng.uniform(9, 16))]), w=1.5, amp=0.3, again=0.0, over=0.0, drift=0.0,
                         breaks=False)
    gx, gy = look
    for ex in (-54, 54):  # the eyes, the brows
        ey = -24
        pen.line(L(bez((ex - 24, ey), (ex - 9, ey - 10), (ex + 11, ey - 10), (ex + 24, ey + 1))), w=3.6, again=0.2)
        pen.line(L(bez((ex - 18, ey + 7), (ex - 6, ey + 12), (ex + 8, ey + 12), (ex + 19, ey + 7))), w=1.5)
        (px, py), = L([(ex + 8 * gx, ey + 3 + 3 * gy)])
        pen.poly(arc(px, py, 7.5 * s / 0.55, 6.5 * s / 0.55, 0, 360, 12))
        pen.line(L(bez((ex - 28, ey - 30), (ex - 10, ey - 38), (ex + 10, ey - 38), (ex + 28, ey - 31))), w=4.4, again=0.2)
    pen.line(L(bez((2, -14), (-4, 12), (-16, 28), (-6, 38))), w=2.8)  # the nose
    pen.line(L(bez((-6, 38), (6, 43), (20, 38), (24, 30))), w=2.8)
    if mouth == "talk":
        pen.line(L(loop_pts(rng, 4, 98, 22, 12)), w=2.8, over=0.0, breaks=False)
    elif mouth == "smile":
        pen.line(L(bez((-36, 90), (-12, 106), (14, 106), (38, 90))), w=3.2)
        pen.line(L(bez((-14, 116), (-4, 119), (8, 119), (16, 116))), w=1.6, over=0.0, again=0.0)
    else:
        pen.line(L(bez((-30, 98), (-8, 94), (14, 95), (34, 100))), w=3.2)
    if hair == "short":  # cut short: strokes standing up from the hairline
        line_, top = arc(0, -34, 150, 96, 194, 346, 30), arc(4, -44, 160, 186, 186, 354, 30)
        pen.poly(L(line_ + top[::-1]), fill=0)
        pen.line(L(top), w=4.2, again=0.3)
        for k in range(130):
            i = int(rng.uniform(0.0, 0.999) * len(line_))
            (hx_, hy_), (tx, ty) = line_[i], top[min(len(top) - 1, i)]
            f, d = rng.uniform(0.0, 0.8), math.hypot(tx - hx_, ty - hy_) or 1.0
            sx_, sy_ = hx_ + (tx - hx_) * f, hy_ + (ty - hy_) * f
            ln = rng.uniform(12, 24)
            pen.line(L([(sx_, sy_), (sx_ + (tx - hx_) / d * ln, sy_ + (ty - hy_) / d * ln)]), w=rng.uniform(1.2, 2.2), again=0.0, over=1.0,
                     drift=0.0, breaks=False)
    elif hair == "long":  # long, parted in the middle, down over her shoulders
        top = arc(0, -30, 166, 196, 180, 360, 30)
        sides = [[(-150, -40), (-176, 60), (-190, 180), (-176, 300), (-150, 330), (-128, 260), (-130, 120), (-122, 0)],
                 [(150, -40), (176, 60), (190, 180), (176, 300), (150, 330), (128, 260), (130, 120), (122, 0)]]
        for sd in sides:
            pen.poly(L(spline(sd, 6)), fill=0)
            pen.line(L(spline(sd, 6)), w=3.6, again=0.25)
            for k in range(6):
                f = (k + 1) / 7
                pen.line(L(spline([(sd[0][0] * (1 - f * 0.15), -20), (sd[2][0] * (1 - f * 0.22), 170), (sd[3][0] * (1 - f * 0.18), 300)], 6)),
                         w=rng.uniform(1.0, 1.8), again=0.0, over=1.0, drift=0.3, breaks=False)
        cap = top + [(122, -10), (60, -110), (0, -130), (-60, -110), (-122, -10)]
        pen.poly(L(cap), fill=0)
        pen.line(L(top), w=4.2, again=0.3)
        for sx in (-1, 1):  # from the parting, down each side
            for k in range(8):
                f = (k + 1) / 9
                pen.line(L(bez((sx * 4, -218 + 60 * f), (sx * 60 * (0.6 + f), -200 + 50 * f), (sx * 120 * (0.7 + 0.3 * f), -140 + 40 * f),
                               (sx * (124 + 20 * f), -40 + 30 * f), 16)), w=rng.uniform(1.0, 1.9), again=0.0, over=1.0, drift=0.3, breaks=False)
    elif hair == "curly":  # curls all over, a bumpy outline
        th = np.radians(np.linspace(180, 360, 90))
        rr = 1 + 0.07 * np.abs(np.sin(9 * th))
        out = list(zip(176 * rr * np.cos(th), -40 + 196 * rr * np.sin(th)))
        inner = arc(0, -36, 146, 100, 360, 180, 30)
        pen.poly(L(out + inner), fill=0)
        pen.line(L(out), w=4.0, again=0.3)
        for k in range(240):
            a = math.radians(rng.uniform(185, 355))
            rk = rng.uniform(0.35, 0.9)
            cx_, cy_ = 168 * rk * math.cos(a), -40 + 188 * rk * math.sin(a)
            if cy_ > -36 - 100 * math.sqrt(max(0.0, 1 - (cx_ / 146) ** 2)) - 8:
                continue
            pen.line(L(loop_pts(rng, cx_, cy_, rng.uniform(10, 16), rng.uniform(9, 14))), w=rng.uniform(1.3, 2.0), over=0.0, breaks=False, drift=0.2,
                     again=0.0)


def back_table(pen, y0, x0=-40, x1=1120):
    """A table further off: its edge, a band of its top, a few boards; it hides who sits behind it below their chest."""
    pen.poly([(x0, y0), (x1, y0 - 4), (x1, y0 + 150), (x0, y0 + 150)], fill=0)
    pen.line([(x0, y0), (x1, y0 - 4)], w=4.0)
    for x in np.arange(x0 + 90, x1, 150):
        pen.line([(x, y0 + 3), (x + (x - 820) * 0.25, y0 + 120)], w=1.5, amp=1.0, again=0.0, drift=0.5)


def framed(cam):
    """Draws the next things through another camera (zoom, the drawing's point at the middle, where it lands)."""
    class Frame:
        def __enter__(self):
            self.old = list(dt.CAM)
            dt.CAM[:] = cam

        def __exit__(self, *a):
            dt.CAM[:] = self.old
    return Frame()


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


def drawing(variant=0, hair="wavy", beard=True):
    """The first drawing, on white: at his table at night, his head a little on one side, looking down at his
    phone; what he does not dare (questions, talking to people) and his faith, in the bubbles over him."""
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    pen = Hand(img, np.random.default_rng(100 + variant))
    table(pen)
    body(pen)
    head(pen, pen.rng, hx=620.0, hy=962.0, tilt=6.0, hair=hair, beard=beard)
    phone_on_table(pen, orange)
    trail = ((345, 625, 50), (414, 692, 22), (456, 724, 12)) if hair == "wavy" else ((360, 640, 52), (450, 790, 26), (500, 850, 15))
    for bx, by, r, sym in ((250, 470, 120, "?"), (420, 330, 95, "chat"), (165, 720, 82, "cross")) + tuple((x, y, r, None) for x, y, r in trail):
        bubble(pen, bx, by, r, sym)
    return finish(img, orange, variant)


def at_table(seed, wide=False, **face):
    """A new page, and Tony at his table as in the first drawing (his phone lit in front of him), with this face."""
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    pen = Hand(img, np.random.default_rng(seed))
    return img, orange, pen


def tony(pen, orange, wide=False, **face):
    table(pen, wide)
    body(pen)
    head(pen, pen.rng, hx=620.0, hy=962.0, tilt=6.0, **face)
    phone_on_table(pen, orange)


# --- the film, line by line (SCRIPT.md): one drawing each
def scene_2(variant=0):
    """« Moi c'est Tony. »: the thoughts gone, he looks up at us."""
    img, orange, pen = at_table(200 + variant)
    tony(pen, orange, look=(0.12, -0.3), lids=13.5, smile=0.3)
    return finish(img, orange, variant)


def scene_3(variant=0):
    """« Pendant longtemps, j'ai été quelqu'un de renfermé. »: seen from far off, small in a corner of the page,
    shut in his own bubble; all the rest empty."""
    img, orange, pen = at_table(300 + variant)
    with framed([0.42, 620.0, 1150.0, 790.0, 1560.0]):
        tony(pen, orange, worry=0.35)
    inside = Image.new("L", img.size, 0)
    ImageDraw.Draw(inside).ellipse([(782 - 252) * S, (1594 - 274) * S, (782 + 252) * S, (1594 + 274) * S], fill=255)
    for layer in (img, orange):
        layer.paste(0, (0, 0), ImageOps.invert(inside))
    for k, (rx, ry) in enumerate(((262, 282), (256, 290))):
        pen.line(loop_pts(pen.rng, 782, 1594, rx, ry), w=3.4 if k == 0 else 1.8, over=0.0, breaks=False, drift=0.8, again=0.0)
    return finish(img, orange, variant)


def scene_4(variant=0):
    """« Le genre de personne qui n'osait pas poser de questions. »: his question stays stuck over his head,
    squashed against it; he looks up at it."""
    img, orange, pen = at_table(400 + variant)
    tony(pen, orange, look=(0.15, -1.1), lids=13.0, smile=-0.25, worry=0.45)
    bubble(pen, 656, 624, 80, "?", squash=0.74)
    for sx in (-1, 1):  # it strains
        pen.line(bez((656 + sx * 100, 598), (656 + sx * 112, 612), (656 + sx * 112, 638), (656 + sx * 100, 652), 10), w=2.2, over=0.0, again=0.0)
    return finish(img, orange, variant)


def scene_5(variant=0):
    """« Peut-être par peur de dire n'importe quoi… »: what he would say, a tangle in a speech bubble; he eyes it."""
    img, orange, pen = at_table(500 + variant)
    tony(pen, orange, look=(-0.9, -0.35), lids=12.5, smile=-0.3, worry=0.6)
    speech(pen, 300, 560, 215, 165, (436, 900), "scribble")
    return finish(img, orange, variant)


def scene_6(variant=0):
    """« …ou par peur de déranger. »: further off, three people talking and laughing at their table; Tony at his,
    looking at them, his « … » never said."""
    img, orange, pen = at_table(600 + variant)
    for args in ((850, 770, 0.5, "short", (-0.6, 0.2), "talk", True), (690, 800, 0.5, "long", (0.8, 0.1), "smile", False),
                 (1004, 815, 0.5, "curly", (-0.9, 0.1), "smile", False)):
        person(pen, *args)
    back_table(pen, 1012, 560, 1120)
    speech(pen, 852, 560, 108, 66, (846, 650), "talk")
    with framed([0.92, 620.0, 1100.0, 330.0, 1270.0]):
        tony(pen, orange, wide=True, look=(0.95, -0.6), lids=13.0, smile=-0.15, worry=0.4)
    speech(pen, 562, 878, 62, 44, (480, 1000), "dots")
    return finish(img, orange, variant)


SCENES = [drawing, scene_2, scene_3, scene_4, scene_5, scene_6]


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    drawing(0).save(out / "tony_sketch.png")
    for i, fn in enumerate(SCENES, 1):
        fn(0).save(out / f"scene_{i:02d}.png")
        print(out / f"scene_{i:02d}.png")


if __name__ == "__main__":
    main()
