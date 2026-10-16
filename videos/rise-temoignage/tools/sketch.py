"""Tony drawn the way his very first drawing was (draw_test.py), the style he wants, in black on white paper:
lines put down once, freehand, never gone back over to clean them. A felt pen and no ruler, no compass: each
stroke wanders a little on its way, swells where the pen lands and thins where it lifts, runs past its ends; a
long one is sometimes done in two goes; a circle never quite closes; hatching stops near the edge, not on it;
here and there a line was drawn twice, a little beside itself.
Drawn as a grown man, not the way a child draws: his head turned a little and built in depth, so that all of it
turns together (a man's long face and jaw, a real nose, eyes under their lids, low straight brows, a short
beard), a broad neck and shoulders, the light from our left giving the side away from it its hatching; a plain
table, his phone lying on it. No hands: his arms go down behind the table.
Usage: python3 tools/sketch.py  -> renders/tony_sketch_hello.png (« Moi c'est Tony. »)
                                   renders/tony_sketch_phone.png (bowed over his phone)
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


def spline(pts, n=8):
    """A smooth curve through the points (Catmull-Rom), in 2D or 3D."""
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return [tuple(q) for q in out]


def hull(pts):
    """The convex outline round points, in order."""
    p = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
            up.pop()
        up.append(q)
    return lo[:-1] + up[:-1]


def ellipsoid(c, r, n=40):
    out = []
    for y in np.linspace(c[1] - r[1] * 0.999, c[1] + r[1] * 0.999, n):
        k = math.sqrt(max(0.0, 1 - ((y - c[1]) / r[1]) ** 2))
        out += [(c[0] + r[0] * k * math.sin(ph), y, c[2] + r[2] * k * math.cos(ph)) for ph in np.linspace(0, 2 * math.pi, 2 * n, endpoint=False)]
    return out


class Head:
    """His head: turned towards our left by yaw degrees, nodding down by pitch, leaning by roll, seen from in front
    without perspective. Its points are given in 3D (x to our right, y down, z towards us, from the middle of his
    head at the height of his eyes), or across his face as if seen straight on, then laid onto it."""
    YS = [-100, -60, -30, 0, 40, 80, 110, 140, 170, 192, 202, 206]
    A = [146, 148, 150, 151, 148, 140, 126, 106, 74, 44, 22, 0]  # half his face's width
    ZC = [176, 182, 184, 176, 176, 178, 180, 176, 170, 166, 165, 164]  # how far forward its middle is
    ZS = [40, 45, 55, 62, 62, 55, 50, 62, 100, 138, 152, 160]  # and its edges

    def __init__(self, hx, hy, yaw=0.0, pitch=0.0, roll=0.0, k=1.0):
        self.hx, self.hy, self.yaw, self.k = hx, hy, yaw, k
        t, f, r = (math.radians(v) for v in (yaw, pitch, roll))
        self.ct, self.st, self.cf, self.sf, self.cr, self.sr = math.cos(t), math.sin(t), math.cos(f), math.sin(f), math.cos(r), math.sin(r)

    def a(self, y):
        return float(np.interp(y, self.YS, self.A))

    def zs(self, y):
        return float(np.interp(y, self.YS, self.ZS))

    def surf(self, x, y):
        a = max(1.0, self.a(y))
        zc, zs = float(np.interp(y, self.YS, self.ZC)), self.zs(y)
        return zc - (zc - zs) * min(1.0, abs(x) / a) ** 2.5

    def view(self, x, y, z):
        """Across, down and towards us, once turned."""
        X = x * self.ct - z * self.st
        Z = x * self.st + z * self.ct
        return X, y * self.cf + Z * self.sf, Z * self.cf - y * self.sf

    def p(self, x, y, z):
        X, Y, _ = self.view(x, y, z)
        return (self.hx + (X * self.cr - Y * self.sr) * self.k, self.hy + (X * self.sr + Y * self.cr) * self.k)

    def q(self, pts):
        return [self.p(*c) for c in pts]

    def f(self, pts, lift=0.0):
        return [self.p(x, y, self.surf(x, y) + lift) for x, y in pts]

    def facing(self, n):
        return self.view(*n)[2] > 0


CAP_C = (0.0, -60.0, -8.0)  # the middle of his skull
CAP_R = (156.0, 184.0, 194.0)  # the cap round it: half its width, height, depth


def cap_pt(phi, y):
    """The cap at the angle phi round his head (0 at his forehead, growing towards his left ear) and the height y."""
    (cx, cy, cz), (ax, ay, az) = CAP_C, CAP_R
    k = math.sqrt(max(0.0, 1 - ((y - cy) / ay) ** 2))
    return (cx + ax * k * math.sin(phi), y, cz + az * k * math.cos(phi))


def cap_normal(x, y, z):
    (cx, cy, cz), (ax, ay, az) = CAP_C, CAP_R
    return ((x - cx) / ax ** 2, (y - cy) / ay ** 2, (z - cz) / az ** 2)


def band_y(phi):
    """Its lower edge: high on his forehead (it is worn backwards), lower over his ears, lower still behind."""
    return -66 - 30 * math.cos(phi) - 4 * math.cos(2 * phi)


def runs(flags):
    """The stretches where flags hold, as (start, end) index pairs."""
    e = np.diff(np.r_[0, np.asarray(flags, int), 0])
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def draw_head(pen, hd, look=(0.0, 0.0), lids=12.0, smile=0.0, lift=0.0, worry=0.0):
    """His head: the end of his cap's peak behind it; the outline of his face, his ear; the shade on the side away
    from the light; his short beard; his mouth, nose, eyes and brows; his glasses; his cap.
    look: where his eyes go (-1..1 across and down, on his face), lids: how open (8 heavy, 13 open), smile 0..1,
    lift: his brows raised, worry: their inner ends raised."""
    rng = pen.rng
    turned = hd.yaw >= 6
    band3 = [cap_pt(ph, band_y(ph)) for ph in np.linspace(-math.pi, math.pi, 721)]
    seen = [i for i, c in enumerate(band3) if hd.facing(cap_normal(*c))]
    band3 = band3[seen[0]:seen[-1] + 1]  # the band, from the far side of his head round to the near side
    band = hd.q(band3)

    # the end of the cap's peak, behind his head
    phs = np.linspace(math.pi / 2, 3 * math.pi / 2, 41)
    inner = [cap_pt(ph, band_y(ph)) for ph in phs]
    outer = [(x + 125 * math.cos(ph - math.pi) * math.sin(ph), y + 16 * math.cos(ph - math.pi), z + 125 * math.cos(ph - math.pi) * math.cos(ph))
             for (x, y, z), ph in zip(inner, phs)]
    peak = hd.q(inner + outer[::-1])
    pen.poly(peak, fill=0)
    pen.hatch(peak, 115, 7, w=1.0)
    pen.line(hd.q(outer), w=3.0)

    # his face, and on the near side his jaw up to his ear and the back of his head; it hides what is behind
    far = hd.q([(-hd.a(y), y, hd.zs(y)) for y in np.linspace(-72, 206, 48)])
    if turned:
        near = hd.q([(hd.a(y), y, hd.zs(y)) for y in np.linspace(206, 112, 18)][1:] + [(130, 96, 36), (136, 80, 24), (140, 64, 14)])
        skull = hull(hd.q(ellipsoid(CAP_C, (150, 178, 188))))
        back = sorted([q for q in skull if q[0] > hd.hx + 70 and band[-1][1] - 6 < q[1] < hd.hy + 82], key=lambda q: q[1])
    else:
        near = hd.q([(hd.a(y), y, hd.zs(y)) for y in np.linspace(206, -72, 48)][1:])
        back = []
    pen.poly(far + near + back[::-1] + band[::-1], fill=0)
    if back:
        pen.line(back, w=3.6)
    pen.line(far, w=4.2, again=0.3)
    pen.line(far[-1:] + near, w=5.0, again=0.3)

    # his ear(s): the rim, the fold inside, the little flap in front
    for side in ((1,) if turned else (-1, 1)):
        def E(zr, yr, out):
            return (side * (146 + out), 12 + yr, -18 + zr)
        rim = [E(*c) for c in spline([(8, -32, 2), (-6, -42, 8), (-24, -38, 13), (-38, -20, 17), (-42, 4, 18), (-36, 28, 16), (-24, 44, 12),
                                      (-10, 54, 7), (2, 50, 4), (6, 40, 2)], 4)]
        pen.poly(hd.q(rim + [E(10, 30, 0), E(10, -20, 0)]), fill=0)
        pen.line(hd.q(rim), w=3.4)
        pen.line(hd.q([E(*c) for c in spline([(-4, -28, 6), (-20, -26, 10), (-28, -6, 12), (-24, 18, 10), (-12, 32, 6)], 4)]), w=1.8, again=0.0)
        pen.line(hd.q([E(2, 2, 2), E(6, 10, 3), E(4, 20, 2)]), w=1.6, again=0.0, over=1.0)
        # his hair, cut short, behind it and in front of it below the cap
        for k in range(26):
            y = rng.uniform(band_y(2.0) + 4, 66)
            ph = rng.uniform(1.75, 2.15) if k < 18 else rng.uniform(1.2, 1.32)
            x, _, z = cap_pt(side * ph, y)
            x, z = x * 0.965, z * 0.965
            pen.line(hd.q([(x, y, z), (x - side * 1.5, y + rng.uniform(7, 12), z)]), w=1.3, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)

    if turned:  # the side of his face, away from the light
        ys = np.linspace(-58, 112, 18)
        side_in = [(0.72 * hd.a(y), y, hd.surf(0.72 * hd.a(y), y)) for y in ys]
        side_out = [(146, -58, 10), (148, -20, 6), (148, 20, 6), (144, 56, 10), (140, 64, 14), (130, 96, 36), (126, 112, 50)]
        pen.hatch(hd.q(side_in + side_out[::-1]), 115, 12, w=0.95)

    # his beard, kept short: along his jaw and over his chin, a little over his lip
    for k in range(190):
        y = rng.uniform(26, 205)
        a = hd.a(y)
        x = rng.choice((-1, 1)) * (a - min(a, 56.0, rng.exponential(17)))
        if abs(x) < 54 and 98 < y < 142:  # not on his lips
            continue
        pen.line(hd.f([(x, y), (x + rng.uniform(-2, 2), y + rng.uniform(6, 12))], lift=1), w=1.15, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)
    lip = bez((-48, 96), (-18, 85), (20, 85), (50, 96), 101)
    for t in rng.uniform(0.04, 0.96, 26):
        x, y = lip[int(t * 100)]
        y += rng.uniform(-4, 3)
        pen.line(hd.f([(x, y), (x + 0.08 * x, y + rng.uniform(5, 8))], lift=2), w=1.1, amp=0.3, again=0.0, over=0.0, drift=0.0, breaks=False)

    # his mouth
    sm = smile
    pen.line(hd.f(bez((-46, 112 - 6 * sm), (-16, 106 + 7 * sm), (18, 107 + 7 * sm), (48, 112 - 6 * sm), 24), lift=2), w=3.2)
    pen.line(hd.f(bez((-22, 129 + 2 * sm), (-6, 135 + 3 * sm), (14, 135 + 3 * sm), (28, 128 + 2 * sm), 16), lift=2), w=2.0)
    if sm > 0.3:
        pen.line(hd.f(bez((-50, 104), (-55, 108), (-55, 114), (-50, 119), 8), lift=2), w=1.6, over=0.0, again=0.0)
        pen.line(hd.f(bez((52, 104), (57, 108), (57, 114), (52, 119), 8), lift=2), w=1.6, over=0.0, again=0.0)

    # his nose: down its far side, round its tip to the near nostril; the shade on its near side
    def N(x, y, pr):
        return (x, y, hd.surf(x, y) + pr)
    pen.line(hd.q(spline([N(-8, -16, 4), N(-12, 14, 10), N(-15, 40, 18), N(-12, 56, 28), N(-4, 64, 36)], 5)), w=2.8)
    pen.line(hd.q(spline([N(-4, 64, 36), N(4, 71, 32), N(12, 73, 22), N(22, 70, 10), N(27, 62, 4), N(23, 54, 6)], 5)), w=2.8)
    pen.line(hd.q([N(-17, 70, 8), N(-25, 64, 3)]), w=2.0, again=0.0)
    pen.hatch(hd.q([N(2, -6, 6), N(6, 30, 16), N(10, 52, 24), N(18, 60, 10), N(16, 30, 4), N(10, 0, 2)]), 115, 7, w=1.0)

    # his eyes: the iris, half under the upper lid; the lid and its crease, a little of the lower lid; the brow
    gx, gy = look
    for o, ex in ((-1, -60.0), (1, 60.0)):
        ey = -4.0
        ix, iy = ex + 8 * gx, ey + 2 + 4 * gy
        pen.poly(hd.f(arc(ix, iy, 8.5, 8.5, 0, 360, 16), lift=1))
        upper = bez((ex - 25 * o, ey + 1), (ex - 10 * o, ey - lids), (ex + 12 * o, ey - lids), (ex + 28 * o, ey + 3), 20)
        lower = bez((ex - 22 * o, ey + 5), (ex - 8 * o, ey + 11 - 3 * sm), (ex + 10 * o, ey + 11 - 3 * sm), (ex + 24 * o, ey + 5), 16)
        pen.poly(hd.f(upper + [(x, y - 22) for x, y in upper[::-1]], lift=2), fill=0)
        pen.poly(hd.f(lower + [(x, y + 16) for x, y in lower[::-1]], lift=2), fill=0)
        (gx_, gy_), = hd.f([(ix - 3, iy - 3)], lift=2)
        pen.disc(gx_ - 2.0, gy_ - 2.0, gx_ + 2.0, gy_ + 2.0, fill=0)
        pen.line(hd.f(upper, lift=2), w=3.6, again=0.2)
        pen.line(hd.f(bez((ex - 18 * o, ey - lids * 0.75 - 7), (ex - 4 * o, ey - lids - 9), (ex + 12 * o, ey - lids - 8), (ex + 24 * o, ey - lids * 0.5 - 6), 14),
                      lift=2), w=1.3, again=0.0, over=1.0)
        pen.line(hd.f(lower[5:], lift=2), w=1.5, again=0.0)
        b = 6 * lift
        brow = bez((ex - 30 * o, ey - 30 - b - 9 * worry), (ex - 10 * o, ey - 37 - b - 5 * worry), (ex + 12 * o, ey - 38 - b), (ex + 34 * o, ey - 30 - b), 18)
        pen.line(hd.f(brow, lift=4), w=5.4, again=0.4)
        for k in range(7):  # its hairs
            x, y = brow[2 + 2 * k]
            pen.line(hd.f([(x - 3 * o, y + 3), (x + 4 * o, y - 4)], lift=4), w=1.6, again=0.0, over=1.0, drift=0.0, breaks=False)

    # his glasses, a little in front of his face
    gz = 192.0
    for o in (-1, 1):
        pen.line(hd.q([(x, y, gz) for x, y in loop_pts(rng, 62 * o, -6, 50, 43)]), w=2.4, amp=0.7, again=0.35, over=0.0, drift=0.6, breaks=False)
    pen.line(hd.q([(x, y, gz + 2) for x, y in bez((-13, -12), (-6, -20), (6, -20), (13, -12), 10)]), w=2.2)
    for o in ((1,) if turned else (-1, 1)):
        pen.line(hd.q([(110 * o, -12, gz - 6), (147 * o, -16, 16)]), w=2.2)

    # his cap: what of it can be seen, over the band
    sil = hull(hd.q(ellipsoid(CAP_C, CAP_R)))
    i0 = min(range(len(sil)), key=lambda i: math.dist(sil[i], band[0]))
    i1 = min(range(len(sil)), key=lambda i: math.dist(sil[i], band[-1]))
    a1 = [sil[(i0 + k) % len(sil)] for k in range((i1 - i0) % len(sil) + 1)]
    a2 = [sil[(i0 - k) % len(sil)] for k in range((i0 - i1) % len(sil) + 1)]
    dome = [band[0]] + min(a1, a2, key=lambda arc_: min(q[1] for q in arc_)) + [band[-1]]
    pen.poly(dome + band[::-1], fill=0)
    shade = [cap_pt(ph, band_y(ph) - 2) for ph in np.linspace(0.95, 2.0, 12)] + [cap_pt(ph, -214) for ph in np.linspace(2.0, 0.95, 12)]
    pen.hatch(hd.q([c for c in shade if hd.facing(cap_normal(*c))] or shade), 115, 11, w=1.1)
    pen.line(dome, w=4.4, again=0.35)
    pen.line(band, w=4.0, again=0.3)
    stitch = [cap_pt(math.atan2(x, z + 8), band_y(math.atan2(x, z + 8)) - 13) for x, _, z in band3[8:-8]]
    pen.line(hd.q(stitch), w=1.3, amp=1.0, again=0.0)
    for ph in (0.0, -math.pi / 3, math.pi / 3, 2 * math.pi / 3):  # its seams, up to the button
        y0 = band_y(ph) - (46 if ph == 0.0 else 14)
        seam = [cap_pt(ph, y) for y in np.linspace(y0, -238, 16)]
        for i, j in runs([hd.facing(cap_normal(*c)) for c in seam]):
            if j - i > 1:
                pen.line(hd.q(seam[i:j]), w=1.9)
    top = cap_pt(0.0, -243)
    if hd.facing(cap_normal(*top)):
        bx, by = hd.p(*top)
        pen.line(loop_pts(rng, bx, by, 9, 7), w=2.4, over=0.0, breaks=False, drift=0.3)
    # the opening over his forehead, his hair in it, the strap across it
    opening = [cap_pt(38 * math.cos(t) / 190, band_y(0) - 46 * math.sin(t)) for t in np.linspace(0, math.pi, 24)]
    pen.poly(hd.q(opening), fill=0)
    for k in range(8):
        s = -28 + 8 * k + rng.uniform(-2, 2)
        y0 = band_y(0) - 12
        pen.line(hd.q([cap_pt(s / 190, y0), cap_pt((s + rng.uniform(-3, 5)) / 190, y0 - 12 - rng.uniform(0, 14) + abs(s) * 0.4)]), w=1.5, again=0.0, over=0.0,
                 drift=0.0, breaks=False)
    pen.line(hd.q(opening), w=2.8, over=3.0)
    pen.line(hd.q([cap_pt(s / 190, band_y(0) - 14) for s in (-44, 0, 44)]), w=2.0, over=4.0)
    for k in range(4):
        bx, by = hd.p(*cap_pt((-24 + 16 * k) / 190, band_y(0) - 7))
        pen.poly(arc(bx, by, 3.2, 2.8, 0, 360, 8))


def bust(pen, hd, nx, ny):
    """His neck, and his shoulders and chest in a plain tee, down to the table; turned a little less than his head.
    (nx, ny): the bottom of his neck, at the front."""
    # the neck: down from under his jaw on the far side, from behind his ear on the near side; the muscle from
    # behind his ear to the hollow of his throat; the shade his jaw throws on it
    jaw = hd.q([(hd.a(y) * s, y, hd.zs(y)) for s, y in [(-1, 120), (-1, 150), (-1, 176), (-1, 196), (0, 206), (1, 196), (1, 176), (1, 150), (1, 120)]])
    pen.hatch(jaw + [(x + 4, y + 40) for x, y in jaw[::-1]], 115, 9, w=1.0)
    pen.line(spline([hd.p(-hd.a(150), 150, hd.zs(150)), (nx - 90, ny - 60), (nx - 92, ny + 6)], 6), w=4.0)
    pen.line(spline([hd.p(112, 70, -62), (nx + 98, ny - 62), (nx + 104, ny - 22)], 6), w=4.4)
    pen.line(spline([hd.p(128, 70, -34), (nx + 46, ny - 46), (nx + 4, ny + 4)], 6), w=1.4, again=0.0)
    pen.line(bez((nx - 30, ny - 66), (nx - 23, ny - 60), (nx - 21, ny - 51), (nx - 25, ny - 44), 8), w=1.6, again=0.0, over=1.0)
    # the tee: its ribbed collar; the shoulders, the sleeves, the arms going down behind the table
    cx = nx - 10
    co = arc(cx, ny + 6, 130, 42, 6, 174, 40)
    ci = arc(cx, ny - 6, 106, 28, 174, 6, 40)
    pen.poly(co + ci, fill=0)
    pen.hatch(co + ci, 95, 9, w=1.4)
    pen.line(co, w=3.4)
    pen.line([(cx + 129, ny + 10), (cx + 122, ny - 6), (nx + 104, ny - 20)], w=3.0, over=2.0)  # going round behind his neck
    under = arc(cx, ny + 6, 130, 42, 24, 156, 24)
    pen.hatch(under + [(x, y + 24) for x, y in under[::-1]], 115, 9, w=1.0)
    left = [(cx - 125, ny + 12), (cx - 215, ny + 40), (cx - 290, ny + 74), (cx - 334, ny + 116), (cx - 352, ny + 186), (cx - 354, ny + 262)]
    right = [(nx + 104, ny - 22), (cx + 220, ny + 26), (cx + 320, ny + 72), (cx + 370, ny + 118), (cx + 392, ny + 196), (cx + 396, ny + 258)]
    pen.line(spline(left, 6), w=4.4, again=0.3)
    pen.line(spline(right, 6), w=5.0, again=0.3)
    pen.line(spline([(cx - 246, ny + 166), (cx - 247, ny + 230), (cx - 252, 1482)], 6), w=3.4)  # the insides of his arms, from the armpits
    pen.line(spline([(cx + 272, ny + 172), (cx + 273, ny + 236), (cx + 278, 1482)], 6), w=3.8)
    pen.line([(cx - 356, ny + 262), (cx - 300, ny + 271), (cx - 247, ny + 268)], w=2.8)  # the sleeves' hems
    pen.line([(cx + 273, ny + 270), (cx + 336, ny + 268), (cx + 398, ny + 258)], w=2.8)
    pen.line([(cx - 347, ny + 268), (cx - 349, 1482)], w=4.0)  # his arms below them
    pen.line([(cx + 389, ny + 264), (cx + 391, 1482)], w=4.6)
    pen.line(bez((cx - 244, ny + 176), (cx - 226, ny + 188), (cx - 206, ny + 206), (cx - 192, ny + 230), 12), w=1.9)  # folds from the armpits
    pen.line(bez((cx + 270, ny + 182), (cx + 252, ny + 194), (cx + 232, ny + 214), (cx + 220, ny + 240), 12), w=1.9)
    pen.hatch([(cx + 272, ny + 172), (cx + 278, 1470), (cx + 212, 1470), (cx + 224, ny + 236)], 115, 11, w=1.1)  # the shade down his near side
    pen.hatch([(cx + 389, ny + 268), (cx + 391, 1470), (cx + 356, 1470), (cx + 358, ny + 272)], 115, 9, w=1.0)


def table(pen, vp):
    """The table: its far edge just in front of him, two seams between its boards running towards us, a little
    grain; it hides what goes down behind it."""
    pen.poly([(-20, 1474), (1100, 1461), (1100, 1940), (-20, 1940)], fill=0)
    pen.line([(-10, 1475), (1090, 1461)], w=4.6, again=0.2)

    def on_board(xe, u):  # along the line from the vanishing point through the edge at xe, u from the edge (0) to the bottom (1)
        ye = 1475 - 14 * (xe + 10) / 1100
        k = (ye + (1940 - ye) * u - vp[1]) / (ye - vp[1])
        return (vp[0] + (xe - vp[0]) * k, vp[1] + (ye - vp[1]) * k)
    for xe, u1 in ((300, 0.9), (790, 1.0)):
        pen.line([on_board(xe, 0.0), on_board(xe, u1)], w=2.0, again=0.1)
    for xe, u0, u1 in ((60, 0.15, 0.45), (180, 0.4, 0.75), (420, 0.1, 0.32), (560, 0.5, 0.95), (680, 0.2, 0.44), (900, 0.3, 0.7), (1010, 0.08, 0.3)):
        pen.line([on_board(xe, u) for u in np.linspace(u0, u1, 6)], w=1.1, amp=1.0, again=0.0, drift=0.8)


def phone_on_table(pen, orange, quad):
    """His phone lying on the table: its edge, the screen with RISE's flame coloured in orange, its shadow."""
    (fl, fr, nr, nl) = quad  # far left, far right, near right, near left
    pen.hatch([(nl[0] + 4, nl[1] + 6), (nr[0] + 6, nr[1] + 4), (nr[0] + 26, nr[1] + 10), (nl[0] + 18, nl[1] + 16)], 170, 4, w=1.0)
    side = [(nl[0], nl[1]), (nl[0] + 1, nl[1] + 8), (nr[0] + 1, nr[1] + 8), (nr[0], nr[1])]
    pen.poly(side, fill=0)
    pen.line(side, w=2.6, over=2.0, again=0.0)
    ph = rounded(quad, 12, 4)
    pen.poly(ph, fill=0)
    pen.line(ph + ph[:3], w=3.4, over=0.0, breaks=False, again=0.3)

    def on_screen(u, v):  # the screen, inside the phone's edge: u across, v from far to near
        u, v = 0.07 + 0.86 * u, 0.12 + 0.76 * v
        a = (fl[0] + (fr[0] - fl[0]) * u, fl[1] + (fr[1] - fl[1]) * u)
        b = (nl[0] + (nr[0] - nl[0]) * u, nl[1] + (nr[1] - nl[1]) * u)
        return (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v)
    scr = [on_screen(u, v) for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
    pen.line(scr + scr[:1], w=1.4, over=2.0, breaks=False, again=0.0, corners=True)
    flame = OUTLINE["flame"][0]
    xs, ys = [q[0] for q in flame], [q[1] for q in flame]
    fx, fy, fw, fh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    pts = [on_screen(0.5 + ((x - fx) / fh - fw / fh / 2) * 0.3, 0.12 + (y - fy) / fh * 0.76) for x, y in flame[::3]]
    ImageDraw.Draw(orange).polygon([tuple(q) for q in P([(x + 2, y - 1) for x, y in pts])], fill=255)  # coloured in quickly
    pen.line(pts + pts[:2], w=1.7, amp=0.5, over=0.0, breaks=False, again=0.0, drift=0.3)


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


PHONE = [(232, 1556), (430, 1546), (446, 1622), (236, 1634)]
FRAME = [1.1, 560.0, 1250.0, 560.0, 1250.0]  # the camera a little closer than the drawing: zoom, the point it is about, where it lands


def hello(variant=0):
    """« Moi c'est Tony. »: at his table, his head turned a little, he looks up at us with a small, shy smile."""
    img, orange, pen = layers(variant)
    dt.CAM[:] = FRAME
    hd = Head(560, 856, yaw=18, pitch=4, roll=2, k=1.06)
    bust(pen, hd, 566, 1125)
    table(pen, (560, 860))
    phone_on_table(pen, orange, PHONE)
    draw_head(pen, hd, look=(0.6, -0.5), lids=12.0, smile=0.55, lift=0.2)
    return finish(img, orange, variant)


def bowed(variant=0):
    """« J'ai créé un réseau social… alors que j'ose même pas parler aux gens. »: bowed over his phone."""
    img, orange, pen = layers(variant)
    dt.CAM[:] = FRAME
    hd = Head(552, 890, yaw=12, pitch=22, roll=5, k=1.06)
    bust(pen, hd, 566, 1125)
    table(pen, (560, 860))
    phone_on_table(pen, orange, PHONE)
    draw_head(pen, hd, look=(-0.5, 1.2), lids=1.0, smile=0.0, worry=0.35)
    return finish(img, orange, variant)


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    for name, fn in (("tony_sketch_hello", hello), ("tony_sketch_phone", bowed)):
        fn(0).save(out / f"{name}.png")
        print(out / f"{name}.png")


if __name__ == "__main__":
    main()
