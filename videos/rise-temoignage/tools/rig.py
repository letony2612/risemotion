"""Characters drawn like engravings, posed again for every drawing: the rig.

A head is an ellipsoid turned in space (yaw, pitch, roll): its features sit on its surface, so they slide and
foreshorten when it turns; its strokes wrap around it, each as wide as the light along it (the light comes
from the upper left); the hair is combed back over a second shell; the beard is dots. A body is drawn flat:
a torso, arms of two bones (IK), hands. Everything goes through draw_test's camera.
"""
import math
import zlib

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull

import draw_test as dt
import ink
from draw_test import Pen

W, H, S = 1080, 1920, dt.S
LIGHT = ink.LIGHT


def seed(key):
    return zlib.crc32(key.encode()) % 100000


def clip01(x):
    return min(1.0, max(0.0, x))


def lerp(a, b, u):
    return a + (b - a) * u


class Canvas:
    """One drawing: its white ink, and the coloured inks (orange for RISE's flame, red for the teacher's pen)."""

    def __init__(self, v):
        self.v = v
        self.white = Image.new("L", (W * S, H * S), 0)
        self.inks = {"orange": None, "red": None}

    def layer(self, name="white"):
        if name == "white":
            return self.white
        if self.inks[name] is None:
            self.inks[name] = Image.new("L", (W * S, H * S), 0)
        return self.inks[name]

    def rng(self, key):
        return np.random.default_rng(seed(key) * 7 + self.v)

    def pen(self, key, layer="white"):
        return Pen(self.layer(layer), self.rng(key))

    def solid(self, poly, fill=0):
        """A shape filled black: it hides everything drawn behind it, in every ink."""
        pts = [(x * S, y * S) for x, y in ink.to_screen(poly)]
        if len(pts) < 3:
            return
        ImageDraw.Draw(self.white).polygon(pts, fill=fill)
        if fill == 0:
            for im in self.inks.values():
                if im is not None:
                    ImageDraw.Draw(im).polygon(pts, fill=0)

    def fill(self, poly, value=255, layer="white"):
        pts = [(x * S, y * S) for x, y in ink.to_screen(poly)]
        if len(pts) > 2:
            ImageDraw.Draw(self.layer(layer)).polygon(pts, fill=value)

    def disc(self, x, y, r, value=255, layer="white"):
        (X, Y), = ink.to_screen([(x, y)])
        rr = r * dt.CAM[0] * S
        ImageDraw.Draw(self.layer(layer)).ellipse([X * S - rr, Y * S - rr, X * S + rr, Y * S + rr], fill=value)

    def picture(self):
        w = self.white.resize((W, H), Image.LANCZOS)
        rgb = Image.merge("RGB", (w, w, w))
        for name, col in (("orange", (255, 109, 0)), ("red", (226, 40, 40))):
            im = self.inks[name]
            if im is not None and im.getbbox():
                rgb.paste(col, (0, 0), im.resize((W, H), Image.LANCZOS))
        return rgb


def rotmat(yaw, pitch, roll):
    """yaw > 0 turns the face to the viewer's right, pitch > 0 looks up, roll > 0 tilts it clockwise."""
    y, p, r = map(math.radians, (yaw, pitch, roll))
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    Rz = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def norm(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def gauss2(x, y, cx, cy, sx, sy):
    return np.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def hull_arc(P, i0, i1, through):
    """Of a closed polygon P (Nx2), the run of points from index i0 to i1 that passes through index `through`."""
    n = len(P)
    fwd = [(i0 + k) % n for k in range((i1 - i0) % n + 1)]
    if through in fwd:
        return P[fwd]
    back = [(i0 - k) % n for k in range((i0 - i1) % n + 1)]
    return P[back]


FILL = norm(np.array([0.78, 0.05, 0.62]))  # a weak light from the right
RIM = norm(np.array([0.95, -0.2, -0.3]))  # a light from behind on the right: a thin bright edge


def shade(nrm, key=1.0, fill=0.16, rim=0.9, amb=0.04):
    """Key light from the upper left, a little fill from the right, a rim on the right edge."""
    I = amb + key * np.clip(nrm @ LIGHT, 0, 1) + fill * np.clip(nrm @ FILL, 0, 1)
    return I + rim * np.clip(nrm @ RIM, 0, 1) ** 3


class Head:
    """An ellipsoid head at (cx, cy) in the world, s world px per head unit, turned by (yaw, pitch, roll),
    shaped like a face: fuller cheeks, narrower temples and chin.
    Head units: x to the viewer's right, y down, z toward the viewer, from the head's centre."""

    def __init__(self, cx, cy, s, yaw=0.0, pitch=0.0, roll=0.0, a=90.0, b=110.0, c=98.0, shape=(0.07, 0.06, 0.12)):
        self.cx, self.cy, self.s = cx, cy, s
        self.a, self.b, self.c = a, b, c
        self.R = rotmat(yaw, pitch, roll)
        self.cheek, self.temple, self.chin = shape

    def prof(self, y):
        return (1 + self.cheek * np.exp(-((y - 22) / 34) ** 2) - self.temple * np.exp(-((y + 64) / 30) ** 2)
                - self.chin * np.exp(-((y - 110) / 26) ** 2))

    def P3(self, pts3):
        """Head points (Nx3) -> world points (Nx2), and how far toward the viewer each is."""
        p = np.asarray(pts3, float).reshape(-1, 3).copy()
        p[:, 0] *= self.prof(p[:, 1])
        A = p @ self.R.T
        return np.stack([self.cx + self.s * A[:, 0], self.cy + self.s * A[:, 1]], 1), A[:, 2]

    def zf(self, x, y, grow=0.0):
        a, b, c = self.a + grow, self.b + grow, self.c + grow
        return c * np.sqrt(np.clip(1 - (x / a) ** 2 - (y / b) ** 2, 0, 1))

    def on(self, pts2, dz=0.0, grow=0.0):
        """Points of the face, given as seen from the front (x, y), placed on its surface."""
        p = np.asarray(pts2, float).reshape(-1, 2)
        z = self.zf(p[:, 0], p[:, 1], grow) + dz
        return np.column_stack([p, z])

    def at(self, pts2, dz=0.0, grow=0.0):
        return self.P3(self.on(pts2, dz, grow))[0]

    def normals(self, pts3, radii=None, centre=(0, 0, 0)):
        a, b, c = radii or (self.a, self.b, self.c)
        p = np.asarray(pts3, float).reshape(-1, 3) - np.asarray(centre, float)
        n = norm(np.column_stack([p[:, 0] / a ** 2, p[:, 1] / b ** 2, p[:, 2] / c ** 2]))
        return n @ self.R.T

    def shell(self, radii, centre=(0, 0, 0), n_lat=25, n_lon=48, keep=None, warp=None):
        """Sample points of an ellipsoid (head units), and their positions in the world."""
        la, lo = np.meshgrid(np.linspace(-math.pi / 2, math.pi / 2, n_lat), np.linspace(-math.pi, math.pi, n_lon, endpoint=False))
        a, b, c = radii
        p = np.column_stack([(a * np.cos(la) * np.sin(lo)).ravel(), (b * np.sin(la)).ravel(), (c * np.cos(la) * np.cos(lo)).ravel()])
        p = p + np.asarray(centre, float)
        if keep is not None:
            p = p[keep(p)]
        if warp is not None:
            p = warp(p)
        return p, self.P3(p)[0]

    def outline(self, radii=None, centre=(0, 0, 0), keep=None, warp=None):
        p, w = self.shell(radii or (self.a, self.b, self.c), centre, keep=keep, warp=warp)
        h = ConvexHull(w)
        return w[h.vertices], p[h.vertices]

    def light_at(self, X, Y, fn, grow=0.0):
        """How lit the front of the head is under world points (X, Y): fn(normals) (roughly, for dots)."""
        a, b, c = self.a + grow, self.b + grow, self.c + grow
        u = (np.asarray(X, float) - self.cx) / self.s
        v = (np.asarray(Y, float) - self.cy) / self.s
        u = u / self.prof(v)
        Rt = self.R.T
        base = np.stack([u, v], -1) @ Rt[:, :2].T
        d = Rt[:, 2]
        r = np.array([a, b, c])
        A = np.sum((d / r) ** 2)
        B = 2 * np.sum(base * d / r ** 2, -1)
        C = np.sum((base / r) ** 2, -1) - 1
        w = (-B + np.sqrt(np.clip(B * B - 4 * A * C, 0, None))) / (2 * A)
        p = base + w[..., None] * d
        n = norm(p / r ** 2) @ self.R.T
        return np.clip(fn(n.reshape(-1, 3), p.reshape(-1, 3)).reshape(np.shape(X)), 0, 1)


def rings(hd, radii, centre, normal, gap_world, light_fn, n_pts=120, keep=None):
    """Strokes wrapping a head's shell: its sections by parallel planes (normal in head units), the parts
    facing the viewer, with the light along them. Returns [(world pts, light)]."""
    r = np.asarray(radii, float)
    m = norm(normal)
    mr = m * r
    k = np.linalg.norm(mr)
    n1 = mr / k
    e1 = norm(np.cross(n1, [0.0, 0.0, 1.0]) if abs(n1[2]) < 0.9 else np.cross(n1, [1.0, 0.0, 0.0]))
    e2 = np.cross(n1, e1)
    th = np.linspace(0, 2 * math.pi, n_pts)
    out = []
    step = gap_world * k / np.linalg.norm(m * r * r / r) if False else gap_world
    for o in np.arange(-k + step * 0.5, k, step):
        o1 = o / k
        rho = math.sqrt(max(0.0, 1 - o1 * o1))
        u = n1 * o1 + rho * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2)
        p = u * r + np.asarray(centre, float)
        nrm = hd.normals(p, tuple(r), centre)
        vis = nrm[:, 2] > 0.03
        if keep is not None:
            vis &= keep(p)
        if not vis.any():
            continue
        w, _ = hd.P3(p)
        sw = ink.to_screen(w)
        vis &= (sw[:, 0] > -30) & (sw[:, 0] < W + 30) & (sw[:, 1] > -30) & (sw[:, 1] < H + 30)
        if not vis.any():
            continue
        I = light_fn(nrm, p)
        idx = np.flatnonzero(vis)
        for run in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
            if len(run) > 1:
                out.append((w[run], I[run]))
    return out


# --- faces: what makes a character
TONY = dict(a=90, b=108, c=98, shape=(0.07, 0.06, 0.1), eye=(33, -4), eye_w=13.5, eye_h=7.2, brow_y=-25, mouth_y=58,
            mouth_w=21, beard=True, glasses=True, hair="slick", nose=1.0, droop=0.14)
KID = dict(a=92, b=100, c=96, shape=(0.06, 0.03, 0.06), eye=(31, 4), eye_w=14.5, eye_h=8.6, brow_y=-20, mouth_y=52,
           mouth_w=16, beard=False, glasses=True, hair="kid", nose=0.72, droop=0.08)

MATE_A = dict(a=90, b=100, c=95, shape=(0.06, 0.03, 0.08), eye=(31, 4), eye_w=14, eye_h=8.4, brow_y=-20, mouth_y=52, mouth_w=17,
              beard=False, glasses=False, hair="short", nose=0.75, droop=0.05)
MATE_B = dict(MATE_A, hair="pony", hair_light=1.6, eye_h=8.8, mouth_w=15)
TEACHER = dict(a=88, b=112, c=96, shape=(0.04, 0.05, 0.1), eye=(32, -4), eye_w=13, eye_h=6.6, brow_y=-25, mouth_y=58, mouth_w=20,
               beard=False, glasses=True, hair="short", nose=1.1, droop=0.3, hair_light=1.7)
ADULT_W = dict(a=86, b=106, c=94, shape=(0.05, 0.05, 0.12), eye=(31, -4), eye_w=13.5, eye_h=7.4, brow_y=-24, mouth_y=56, mouth_w=18,
               beard=False, glasses=False, hair="long", nose=0.9, droop=0.1)
ADULT_M = dict(TEACHER, glasses=False, hair_light=1.0, droop=0.1)
ADULT_B = dict(ADULT_M, beard=True, hair="slick", nose=1.0)


def sockets(face):
    """Where the face is darker: the eyes' hollows, the nose's shadow side, under the nose and the brows."""
    ex, ey = face["eye"]

    def f(x, y):
        k = np.ones_like(x)
        for sx in (-1, 1):
            k *= 1 - 0.5 * gauss2(x, y, sx * ex, ey + 2, 20, 12)
        k *= 1 - 0.45 * gauss2(x, y, 0, ey - 14, 50, 5)  # under the brow ridge
        k *= 1 - 0.55 * gauss2(x, y, 0, 42, 20, 6)
        return k
    return f


def draw_head(cv, key, hd, face, ex, prog=1.0, lift=None):
    """A head, engraved. ex: the expression (gaze gx, gy in -1..1, blink, squint, brow, worry, smile, open).
    lift(n, p): more light (the phone's glow from below), from the surface normal n (world) and point p.
    Returns where its lenses are (world polygons) and its skin."""
    a, b, c, s = hd.a, hd.b, hd.c, hd.s
    zc = dt.CAM[0]
    ppu = s * zc  # screen px per head unit
    detail = clip01((ppu - 0.35) / 0.9)
    gap = 6.2 / ppu  # the strokes' spacing: the same on screen whatever the camera
    dark = sockets(face)
    gx, gy = ex.get("gx", 0.0), ex.get("gy", 0.0)
    blink = clip01(face["droop"] + ex.get("blink", 0.0) * (1 - face["droop"]))
    squint = ex.get("squint", 0.0)
    smile, opn = ex.get("smile", 0.0), ex.get("open", 0.0)
    brow, worry = ex.get("brow", 0.0), ex.get("worry", 0.0)
    pen = cv.pen(key + "head")
    my, mw = face["mouth_y"], face["mouth_w"]
    ex0, ey0 = face["eye"]
    ew, eh = face["eye_w"], face["eye_h"]

    def light(nrm, p, **k):
        I = shade(nrm, **k)
        if lift is not None:
            I = I + lift(nrm, p)
        return np.clip(I, 0, 1)

    def skin_light(nrm, p):
        return light(nrm, p) * dark(p[:, 0], p[:, 1])

    style = face["hair"]
    hair_k = face.get("hair_light", 1.0)  # fair hair catches more light
    # --- long hair, or a ponytail: behind everything
    if style in ("long", "pony"):
        if style == "long":
            back_f = [(-a - 6, -50), (-a - 20, 40), (-a - 26, 150), (-a - 12, 236), (-40, 250), (0, 242), (40, 250), (a + 12, 236), (a + 26, 150),
                      (a + 20, 40), (a + 6, -50), (0, -b - 16)]
            z_b = -30
        else:
            back_f = [(a * 0.6, -70), (a + 26, -20), (a + 40, 70), (a + 30, 150), (a + 12, 190), (a + 2, 120), (a * 0.7, 20)]
            z_b = -60
        bw3 = np.array([(x, y, z_b) for x, y in ink.smooth(back_f, closed=True, n=5)])
        bwp = hd.P3(bw3)[0].tolist()
        cv.solid(bwp)
        lines = []
        xs = np.linspace(min(x for x, _ in back_f), max(x for x, _ in back_f), 26)
        for x0 in xs:
            ys = np.linspace(-b - 10, 250, 30)
            p3 = np.column_stack([x0 + 6 * np.sin(ys / 40 + x0), ys, np.full_like(ys, z_b)])
            nx = np.clip((x0 - (a + 30 if style == "pony" else 0)) / (a + 30), -1, 1)
            nrm = norm(np.column_stack([np.full_like(ys, nx), np.zeros_like(ys), np.full_like(ys, math.sqrt(max(0.05, 1 - nx * nx)))])) @ hd.R.T
            lines.append((hd.P3(p3)[0], light(nrm, p3) * 0.8 * hair_k))
        ink.engrave(cv.white, lines, clip=[bwp], lo=0.25, wmax=1.7, prog=prog)
        pen.line(bwp + bwp[:1], w=2.0, amp=0.5)

    # --- ears, behind everything
    for side in (-1, 1):
        ear = np.array([(side * (a - 5), -18, -2), (side * (a + 6), -23, -9), (side * (a + 13), -8, -19), (side * (a + 11), 12, -19),
                        (side * (a + 5), 27, -9), (side * (a - 5), 24, 0)], float)
        inner = np.array([(side * (a + 3), -12, -9), (side * (a + 7), 0, -14), (side * (a + 4), 12, -10)], float)
        w_ear, z_ear = hd.P3(ear)
        if z_ear.mean() < -45:
            continue
        outline = ink.smooth(w_ear.tolist(), n=6)
        cv.solid(outline)
        n_ear = hd.normals(np.array([[side * a, 0, 0]]))
        I_ear = float(light(n_ear, np.zeros((1, 3)))[0])
        ink.hatch(cv.white, [outline], ink.flat(I_ear), cv.rng(key + f"earh{side}"), angle=75, gap=6.0, lo=0.25, wmax=2.0, cross=0)
        pen.line(outline, w=2.4, amp=0.5)
        pen.line(ink.smooth(hd.P3(inner)[0].tolist(), n=6), w=1.7, amp=0.4)

    # --- the hair: a shell over the top, black, combed back in white strands
    hr = np.array([a + 5, b + 15, c + 8], float)
    hc = np.array([0, -8, -5], float)
    if face["hair"] == "kid":
        hr = np.array([a + 7, b + 13, c + 10], float)
        hc = np.array([0, -6, -3], float)
    def hug(p):  # the hair hugs the head toward its lower edge, over the ears
        p = np.array(p, float)
        k = 1 - 0.075 * np.clip((p[:, 1] + 52) / 30, 0, 1) ** 1.5
        p[:, 0] *= k
        return p
    hw, hp = hd.outline(tuple(hr), tuple(hc), keep=lambda p: p[:, 1] < -22, warp=hug)
    hair_poly = hw.tolist()  # a hull: smoothing it would overshoot at its corners
    cv.solid(hair_poly)
    if face["hair"] == "kid":  # a fringe, swept to his left
        hl = [(-88, 4), (-86, -24), (-76, -44), (-56, -50), (-30, -42), (-8, -46), (16, -54), (44, -60), (66, -56), (82, -40), (88, -16), (88, 4)]
    elif style in ("short", "long", "pony"):
        hl = [(-89, 4), (-86, -24), (-78, -44), (-60, -58), (-30, -64), (0, -66), (30, -64), (60, -58), (78, -44), (86, -24), (89, 4)]
    else:  # slicked back: the forehead free
        hl = [(-89, 6), (-87, -24), (-80, -46), (-62, -64), (-34, -74), (0, -77), (34, -74), (62, -64), (80, -46), (87, -24), (89, 6)]
    hl = ink.smooth(hl, n=5)
    hl_w = hd.at(hl, dz=1.0)
    back = norm(np.array([0.0, -0.32, -0.95]))  # slicked back: every strand heads for the back of the head
    half = norm(LIGHT + np.array([0, 0, 1.0]))
    srng = cv.rng(key + "strands")
    strands = []
    n_locks = int(round(12 + 16 * detail))
    for k in range(n_locks):
        u_lock = (k + srng.uniform(0.25, 0.75)) / n_locks
        for j in range(int(2 + 4 * detail)):
            u = u_lock + srng.normal(0, 0.012)
            i = clip01(u) * (len(hl) - 1)
            i0 = min(int(i), len(hl) - 2)
            f = i - i0
            x0 = hl[i0][0] * (1 - f) + hl[i0 + 1][0] * f
            y0 = hl[i0][1] * (1 - f) + hl[i0 + 1][1] * f
            p0 = hd.on([(x0 * 0.98, y0 + 3)])[0]
            d0 = norm((p0 - hc) / hr)
            if face["hair"] == "kid":
                target = norm(np.array([-0.55 - 0.15 * (x0 / a), -0.7, -0.45]))
            elif style == "short":
                target = norm(np.array([0.3 * x0 / a, -0.95, 0.1]))
            else:
                target = norm(back + srng.normal(0, 0.04, 3))
            om = math.acos(float(np.clip(d0 @ target, -1, 1)))
            if om < 1e-3:
                continue
            ts = np.linspace(0, 1, 28) ** 1.15
            dirs = (np.sin((1 - ts) * om)[:, None] * d0 + np.sin(ts * om)[:, None] * target) / math.sin(om)
            lift_h = 1 + (0.06 * np.sin(np.pi * np.clip(ts * 1.6, 0, 1)) if face["hair"] == "slick" else 0.02 * np.sin(np.pi * ts))
            lift_h = lift_h + 0.012 * np.sin(ts * 7 + k * 1.3)
            p = hug(hc + dirs * hr * lift_h[:, None])
            nrm = hd.normals(p, tuple(hr), tuple(hc))
            vis = nrm[:, 2] > -0.05
            w, _ = hd.P3(p)
            I = 0.02 + 0.32 * np.clip(nrm @ LIGHT, 0, 1) + 1.0 * np.clip(nrm @ half, 0, 1) ** 10 + 0.8 * np.clip(nrm @ RIM, 0, 1) ** 3
            if lift is not None:
                I = I + 0.4 * lift(nrm, p)
            I = I * srng.uniform(0.7, 1.15) * hair_k
            if style == "short":  # a short crop: only the start of each strand
                keep_n = int(len(ts) * 0.35)
                vis[keep_n:] = False
            idx = np.flatnonzero(vis)
            if len(idx) > 1:
                strands.append((w[idx], I[idx]))
    srng.shuffle(strands)
    ink.engrave(cv.white, strands, clip=[hair_poly], lo=0.22, hi=0.9, wmax=1.9, prog=prog, rng=cv.rng(key + "strj"))
    pen.line(np.vstack([hair_poly, hair_poly[:1]]).tolist(), w=2.0, amp=0.5)  # its edge (the face will cover what it crosses)

    # --- the face's skin, below the hairline: black, then engraved around its form
    fw, fp = hd.outline()
    i_l = int(np.argmin(np.sum((fw - hl_w[0]) ** 2, 1)))
    i_r = int(np.argmin(np.sum((fw - hl_w[-1]) ** 2, 1)))
    lower = hull_arc(fw, i_r, i_l, int(np.argmax(fp[:, 1])))
    skin = np.vstack([hl_w, lower]).tolist()
    cv.solid(skin)
    r1 = rings(hd, (a, b, c), (0, 0, 0), (0.3, 0.85, 0.75), gap, skin_light)
    ink.engrave(cv.white, r1, clip=[skin], lo=0.26, hi=0.95, wmax=2.4, prog=prog, rng=cv.rng(key + "r1"))
    if detail > 0.5:
        r2 = rings(hd, (a, b, c), (0, 0, 0), (-0.85, 0.5, 0.6), gap * 1.3, skin_light)
        ink.engrave(cv.white, r2, clip=[skin], lo=0.78, hi=1.0, wmax=1.6, prog=prog, rng=cv.rng(key + "r2"))
    if face["hair"] == "slick" and detail > 0.4:  # a few strands fallen on his forehead
        for k, (x0, y0, x1, y1) in enumerate(((-52, -66, -60, -40), (-44, -70, -49, -50), (-36, -72, -46, -58))):
            pts = hd.at(ink.smooth([(x0, y0), ((x0 + x1) / 2 - 4, (y0 + y1) / 2), (x1, y1)], n=5), dz=2.0)
            pen.line(pts.tolist(), w=1.5, amp=0.4)

    # --- the nose: black first, then strokes across it, lit from the left; its wings, its tip
    k_n = face["nose"]

    def nose_dz(y):
        return k_n * 22 * np.clip((y + 14) / 40, 0, 1) ** 1.6

    def nose_w(y):
        return k_n * (6.5 + 9.5 * np.clip((y - 4) / 30, 0, 1) ** 2)
    ys = np.linspace(-14, 36 * k_n + 2, 14)
    left = [(-nose_w(y), y) for y in ys]
    right = [(nose_w(y), y) for y in ys[::-1]]
    nose_f = np.array(left + right)
    nose3 = np.column_stack([nose_f, hd.zf(nose_f[:, 0], nose_f[:, 1]) + nose_dz(nose_f[:, 1]) * 0.6])
    nose_w_ = hd.P3(nose3)[0]
    cv.solid(nose_w_.tolist())
    lines = []
    for y in np.arange(-12, 36 * k_n, gap * 1.1):
        xs = np.linspace(-nose_w(y), nose_w(y), 12)
        nx = xs / max(nose_w(y), 1e-3)
        zb = np.sqrt(np.clip(1 - nx ** 2, 0, 1)) * nose_w(y) * 0.8
        p3 = np.column_stack([xs, np.full_like(xs, y) + 1.5 * nx ** 2, hd.zf(xs, y) + nose_dz(y) * 0.6 + zb])
        nl = norm(np.column_stack([nx, np.full_like(xs, 0.25), np.sqrt(np.clip(1 - nx ** 2, 0.05, 1))])) @ hd.R.T
        lines.append((hd.P3(p3)[0], skin_light(nl, p3) * 1.1))
    ink.engrave(cv.white, lines, clip=[nose_w_.tolist()], lo=0.3, hi=0.95, wmax=2.2, prog=prog)
    for side, wgt in ((-1, 2.3), (1, 1.5)):
        wing = [(side * 7 * k_n, 31 * k_n + 1, 15), (side * 15.5 * k_n, 30 * k_n + 1, 6), (side * 16 * k_n, 36 * k_n, 3), (side * 7 * k_n, 38 * k_n, 8)]
        wp = np.array([(x, y, hd.zf(x, y) + z * k_n) for x, y, z in wing])
        pen.line(ink.smooth(hd.P3(wp)[0].tolist(), n=5), w=wgt, amp=0.35)
        nost = np.array([(side * 6 * k_n + side * 2.5 * math.cos(t), 36 * k_n + 1.4 * math.sin(t), hd.zf(side * 6 * k_n, 36 * k_n) + 10 * k_n)
                         for t in np.linspace(0, 2 * math.pi, 10)])
        cv.solid(hd.P3(nost)[0].tolist())
    tip = np.array([(x, y, hd.zf(x, y) + z) for x, y, z in [(-4 * k_n, 20 * k_n, 22 * k_n), (-2 * k_n, 27 * k_n, 23 * k_n)]])
    pen.line(hd.P3(tip)[0].tolist(), w=2.4, amp=0.3)
    side_line = np.array([(x * k_n, y, hd.zf(x * k_n, y) + nose_dz(y) * 0.6) for x, y in [(7, -8), (9, 10), (12, 24)]])
    pen.line(ink.smooth(hd.P3(side_line)[0].tolist(), n=4), w=1.2, amp=0.3)

    # --- the beard: black over the jaw, its light in dots, tufts on its edge
    beard_outer = None
    if face["beard"]:
        br = (a + 3, b + 4, c + 3)
        bc = (0, 3, 0)
        bw, bp = hd.outline(br, bc, keep=lambda p: p[:, 1] > -6)
        j_l = int(np.argmin(np.sum((bw - hd.at([(-a + 1, 4)])[0]) ** 2, 1)))
        j_r = int(np.argmin(np.sum((bw - hd.at([(a - 1, 4)])[0]) ** 2, 1)))
        outer = hull_arc(bw, j_l, j_r, int(np.argmax(bp[:, 1])))
        beard_outer = outer
        inner_f = [(a - 7, 6), (a - 19, 24), (64, 36), (50, 45), (mw + 12, my - 12), (14, my - 19), (0, my - 20),
                   (-14, my - 19), (-mw - 12, my - 12), (-50, 45), (-64, 36), (-a + 19, 24), (-a + 7, 6)]
        inner = hd.at(ink.smooth(inner_f, n=4), dz=1.0)
        beard = np.vstack([outer, inner]).tolist()
        cv.solid(beard)

        def beard_light(X, Y):
            return np.maximum(0.3, hd.light_at(X, Y, lambda n, p: light(n, p, fill=0.2, rim=1.2), grow=3))
        ink.stipple(cv.white, [beard], beard_light, cv.rng(key + "stip"), density=0.05, lo=0.2, r=1.0)
        tufts = []
        trng = cv.rng(key + "tufts")
        ow = np.asarray(outer)
        Q, NV = [], []
        for i in range(len(ow) - 1):
            p0, p1 = ow[i], ow[i + 1]
            tl = float(np.hypot(*(p1 - p0))) or 1.0
            nv = np.array([(p1 - p0)[1], -(p1 - p0)[0]]) / tl
            for f in np.linspace(0, 1, max(1, min(40, int(tl * zc / 3.5))), endpoint=False):
                Q.append(p0 + (p1 - p0) * f)
                NV.append(nv)
        if Q:
            Q, NV = np.array(Q), np.array(NV)
            sq = ink.to_screen(Q)
            on_screen = (sq[:, 0] > -20) & (sq[:, 0] < W + 20) & (sq[:, 1] > -20) & (sq[:, 1] < H + 20)
            Q, NV = Q[on_screen], NV[on_screen]
            if len(Q):
                I_t = np.maximum(0.42, beard_light(Q[:, 0], Q[:, 1]))
                Ls = trng.uniform(3.5, 8, len(Q)) * s / 1.6
                for q, nv, L_, I_ in zip(Q, NV, Ls, I_t):
                    tufts.append((np.array([q - nv * L_ * 0.7, q + nv * L_ * 0.4]), np.array([I_, I_ * 0.7])))
        ink.engrave(cv.white, tufts, lo=0.3, hi=0.95, wmax=1.5, prog=prog)

    # --- the mouth: the lower lip caught by the light, the line between the lips dark (open, smiling)
    corners = [(-mw - smile * 3, my - smile * 6), (mw + smile * 3, my - smile * 6)]
    upper = ink.smooth([corners[0], (-mw * 0.45, my - 1.5 - smile * 2), (0, my - 1 - smile), (mw * 0.45, my - 1.5 - smile * 2), corners[1]], n=5)
    low_in = ink.smooth([corners[1], (mw * 0.5, my + 1.5 + 13 * opn + smile * 1.5), (0, my + 2 + 16 * opn + smile * 2),
                         (-mw * 0.5, my + 1.5 + 13 * opn + smile * 1.5), corners[0]], n=5)
    lip_bot = np.asarray(ink.smooth([corners[1], (mw * 0.55, my + 9 + 14 * opn), (0, my + 12 + 16 * opn), (-mw * 0.55, my + 9 + 14 * opn), corners[0]], n=5))
    lip_poly = hd.at(np.vstack([low_in, lip_bot[::-1]]), dz=3.0)
    cv.solid(lip_poly.tolist())
    lip_lines = []
    li = np.asarray(low_in)
    for f in (0.18, 0.4, 0.62, 0.84):
        q = li + (lip_bot - li) * f
        p3 = hd.on(q, dz=3.0)
        nl = hd.normals(p3 + np.array([0, -6 + 10 * f, 0]))
        lip_lines.append((hd.P3(p3)[0][1:-1], light(nl, p3)[1:-1] * 1.25 + 0.08))
    ink.engrave(cv.white, lip_lines, clip=[lip_poly.tolist()], lo=0.2, hi=0.85, wmax=2.2)
    if opn > 0.08:
        cv.solid(hd.at(np.vstack([upper, low_in]), dz=3.0).tolist())
        teeth = ink.smooth([(-mw * 0.6, my - 0.5), (0, my + 1.5 * opn), (mw * 0.6, my - 0.5)], n=4)
        pen.line(hd.at(teeth, dz=3.5).tolist(), w=2.4 * min(1, opn * 3), amp=0.3)
    else:
        pen.line(hd.at(upper, dz=3.0).tolist(), w=3.6, amp=0.3, fill=0)
    if not face["beard"]:  # a child's mouth: its line, lit
        pen.line(hd.at(np.asarray(upper)[1:-1], dz=3.2).tolist(), w=1.6, amp=0.3)

    # --- the moustache over it
    if face["beard"]:
        must = ink.smooth([(-mw - 9, my + 1), (-mw - 4, my - 9), (-12, my - 17), (0, my - 15), (12, my - 17), (mw + 4, my - 9), (mw + 9, my + 1),
                           (mw - 2, my - 3), (0, my - 5), (-mw + 2, my - 3)], closed=True, n=4)
        cv.solid(hd.at(must, dz=4.0).tolist())
        mrng = cv.rng(key + "must")
        hairs = []
        for k in range(int(20 + 22 * detail)):
            u = (k + mrng.uniform(0.2, 0.8)) / int(20 + 22 * detail)
            x = -mw - 6 + (2 * mw + 12) * u
            y = my - 12 + 6 * abs(x) / (mw + 8) + mrng.uniform(-2, 2)
            side = 1 if x > 0 else -1
            p3 = hd.on([(x, y)], dz=4.0)
            I = float(light(hd.normals(p3), p3, rim=1.2)[0]) * mrng.uniform(0.8, 1.2)
            hairs.append((hd.at([(x - side * 1, y - 4), (x + side * 3.5, y + 5)], dz=4.5), np.array([I, I * 0.8])))
        ink.engrave(cv.white, hairs, lo=0.25, hi=1.0, wmax=1.5)

    # --- eyes: white, the iris black with its catch of light; the upper lid comes down to blink
    for side in (-1, 1):
        cx = side * ex0
        ic = (cx - side * ew, ey0 + 1.5)
        oc = (cx + side * ew, ey0 - 0.5)
        up = np.asarray(ink.smooth([ic, (cx - side * ew * 0.35, ey0 - eh), (cx + side * ew * 0.4, ey0 - eh * 0.92), oc], n=7))
        lo_ = np.asarray(ink.smooth([ic, (cx - side * ew * 0.3, ey0 + eh * 0.62), (cx + side * ew * 0.4, ey0 + eh * 0.55), oc], n=7))
        m = min(len(up), len(lo_))
        up = up[np.linspace(0, len(up) - 1, m).astype(int)]
        lo_ = lo_[np.linspace(0, len(lo_) - 1, m).astype(int)]
        lid = up + (lo_ - up) * blink
        bot = lo_ + (up - lo_) * squint * 0.5
        if blink < 0.88:
            sclera = np.vstack([lid, bot[::-1]])
            sw = hd.at(sclera, dz=-1.0)
            sw_s = ink.to_screen(sw)
            b_ = ink.box([sw_s], pad=3)
            if b_ is not None:
                mk = ink.local_mask([sw_s], b_)
                lay = Image.new("L", mk.size, 200)
                ix, iy = cx + gx * ew * 0.55, ey0 + gy * eh * 0.4 + 0.5
                r_i = eh * 0.98
                th = np.linspace(0, 2 * math.pi, 26)
                iris = hd.at(np.column_stack([ix + r_i * np.cos(th), iy + r_i * np.sin(th)]), dz=-0.5)
                ImageDraw.Draw(lay).polygon([((x - b_[0]) * S, (y - b_[1]) * S) for x, y in ink.to_screen(iris)], fill=0)
                (X, Y), = ink.to_screen(hd.at([(ix - r_i * 0.32, iy - r_i * 0.36)]))
                rr = max(1.0, 1.5 * ppu * S)
                ImageDraw.Draw(lay).ellipse([(X - b_[0]) * S - rr, (Y - b_[1]) * S - rr, (X - b_[0]) * S + rr, (Y - b_[1]) * S + rr], fill=255)
                x0, y0 = b_[0] * S, b_[1] * S
                region = cv.white.crop((x0, y0, x0 + mk.width, y0 + mk.height))
                cv.white.paste(Image.composite(lay, region, mk), (x0, y0))
            pen.line(hd.at(lid, dz=0.5).tolist(), w=3.2, amp=0.25, fill=0)  # the lashes' line
            crease = lid + np.array([0, -4.5 - 2.5 * (1 - blink)])
            pen.line(hd.at(crease[2:-1], dz=1.0).tolist(), w=1.5, amp=0.35)
            pen.line(hd.at(bot[2:-2], dz=0.2).tolist(), w=1.0, amp=0.3)
        else:  # shut: one line, curved down
            pen.line(hd.at((up + lo_) / 2 + np.array([0, 1.5]), dz=0.5).tolist(), w=2.8, amp=0.35)

    # --- brows: dark bands, their hairs caught by the light
    for side in (-1, 1):
        by = face["brow_y"]
        band = ink.smooth([(side * 13, by - brow * 6 - worry * 7), (side * 34, by - 7 - brow * 7 - worry * 2),
                           (side * 55, by - 1 - brow * 5 + worry * 3)], n=6)
        pen.line(hd.at(band, dz=2.0).tolist(), w=8.0, amp=0.35, fill=0)
        hrng = cv.rng(key + f"brow{side}")
        hairs = []
        bnd = np.asarray(band)
        for k in range(16):
            q = bnd[int((k + 0.5) / 16 * (len(bnd) - 1))] + hrng.normal(0, 0.8, 2)
            p3 = hd.on([q], dz=2.0)
            I = float(light(hd.normals(p3), p3, rim=1.2)[0]) * hrng.uniform(0.85, 1.2)
            hairs.append((hd.at([(q[0] - side * 3, q[1] + 3), (q[0] + side * 3.5, q[1] - 2.5)], dz=2.5), np.array([I, I])))
        ink.engrave(cv.white, hairs, lo=0.3, hi=1.0, wmax=1.4)

    # --- the glasses: round wire, a glint in each lens, the arms to the ears
    lens = []
    if face["glasses"]:
        zp = float(hd.zf(ex0, ey0)) + 13
        th = np.linspace(0, 2 * math.pi, int(48 + 40 * min(1.0, ppu / 2)))
        rx, ry = ew + 13, eh + 17
        for side in (-1, 1):
            cx = side * (ex0 + 2)
            ring = np.column_stack([cx + rx * np.cos(th), ey0 - 1 + ry * np.sin(th), np.full_like(th, zp)])
            rw, _ = hd.P3(ring)
            lens.append(rw)
            pen.line(rw.tolist(), w=2.4, amp=0.3)
            g = np.linspace(3.5, 4.3, 12)
            glint = np.column_stack([cx + 0.74 * rx * np.cos(g), ey0 - 1 + 0.74 * ry * np.sin(g), np.full(12, zp + 1)])
            pen.line(hd.P3(glint)[0].tolist(), w=3.4, amp=0.2)
            (gxw, gyw), = hd.P3(np.array([[cx - 0.3 * rx, ey0 - 1 - 0.38 * ry, zp + 1]]))[0]
            cv.disc(gxw, gyw, 1.8 * s)
            arm = np.array([(side * (ex0 + 2 + rx), ey0 - 4, zp - 2), (side * (a + 2), ey0 - 6, 16)])
            aw, az = hd.P3(arm)
            if az[1] > -20:
                pen.line(aw.tolist(), w=2.1, amp=0.3)
        bridge = np.array([(-ex0 + rx - 2, ey0 - 7, zp), (0, ey0 - 12, zp + 3), (ex0 - rx + 2, ey0 - 7, zp)])
        pen.line(ink.smooth(hd.P3(bridge)[0].tolist(), n=5), w=2.2, amp=0.3)

    # --- its edge, caught all round by the rim light
    pen.line(np.asarray(lower).tolist() if beard_outer is None else np.asarray(beard_outer).tolist(), w=1.8, amp=0.5)
    return dict(lens=lens, skin=skin)


# --- bodies: drawn flat, posed by a few numbers
def ik(sh, wr, l1, l2, elbow=(0.0, 1.0)):
    """Where the elbow goes for a shoulder sh and a wrist wr (2D, two bones), of the two places it could
    go the one furthest along `elbow` (a direction); the wrist is pulled within reach."""
    sh, wr = np.asarray(sh, float), np.asarray(wr, float)
    d = wr - sh
    L = float(np.hypot(*d))
    if L < 1e-6:
        d, L = np.array([0.0, 1.0]), 1.0
    L2 = min(max(L, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    wr = sh + d / L * L2
    a = math.acos(max(-1.0, min(1.0, (l1 * l1 + L2 * L2 - l2 * l2) / (2 * l1 * L2))))
    base = math.atan2(d[1], d[0])
    cands = [sh + l1 * np.array([math.cos(base + b * a), math.sin(base + b * a)]) for b in (1, -1)]
    el = max(cands, key=lambda e: float((e - sh) @ np.asarray(elbow, float)))
    return el, wr


def tube_rings(left, right, light_dir_fn, gap_world, bulge=0.25, n=9):
    """Strokes across a tube (its two outlines), bulging toward its end, lit as a cylinder."""
    left, right = np.asarray(left, float), np.asarray(right, float)
    out = []
    # arc length along the tube's middle, to space the rings
    mid = (left + right) / 2
    seg = np.hypot(*np.diff(mid, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    for d in np.arange(gap_world * 0.5, cum[-1], gap_world):
        i = int(np.searchsorted(cum, d)) - 1
        i = max(0, min(i, len(mid) - 2))
        f = (d - cum[i]) / max(seg[i], 1e-6)
        pl = left[i] + (left[i + 1] - left[i]) * f
        pr = right[i] + (right[i + 1] - right[i]) * f
        ax = mid[i + 1] - mid[i]
        ax = ax / (np.hypot(*ax) + 1e-9)
        t = np.linspace(-1, 1, n)
        across = (pr - pl) / 2
        c = (pl + pr) / 2
        wdt = float(np.hypot(*across))
        pts = c + across * t[:, None] + ax * (bulge * wdt * (1 - t * t))[:, None]
        an = across / (wdt + 1e-9)
        nrm = np.column_stack([an[0] * t, an[1] * t, np.sqrt(np.clip(1 - t * t, 0, 1))])
        out.append((pts, light_dir_fn(nrm)))
    return out


def tube_along(left, right, light_fn, gap_world, n_min=3):
    """Strokes along a tube (an arm), spaced across it, each as lit as its side of the tube."""
    left, right = np.asarray(left, float), np.asarray(right, float)
    wid = float(np.mean(np.hypot(*(right - left).T)))
    n = max(n_min, int(wid / gap_world))
    out = []
    for t in np.linspace(-0.92, 0.92, n):
        u = (t + 1) / 2
        pts = left * (1 - u) + right * u
        across = right - left
        an = across / (np.hypot(*across.T)[:, None] + 1e-9)
        nrm = np.column_stack([an[:, 0] * t, an[:, 1] * t, np.full(len(pts), math.sqrt(max(0.0, 1 - t * t)))])
        I = light_fn(nrm) * (0.85 + 0.15 * np.sin(np.linspace(0, math.pi, len(pts))))
        out.append((pts, I))
    return out



def lit(nrm, key=1.0, fill=0.16, rim=0.9, amb=0.04):
    return np.clip(shade(nrm, key, fill, rim, amb), 0, 1)


def tube(cv, key, chain, widths, gap, prog=1.0, gain=1.0, fill_dark=True, outline=True, lw=2.6, lo=0.27, ends=True):
    """An arm, a finger, a neck: black inside, its outline, strokes around it."""
    left, right = ink.limb(chain, widths, n=6)
    poly = left + right[::-1]
    if fill_dark:
        cv.solid(poly)
    rr = tube_rings(left, right, lambda n: lit(n) * gain, gap)
    ink.engrave(cv.white, rr, clip=[poly], lo=lo, hi=0.95, wmax=2.2, prog=prog, rng=cv.rng(key + "tr"))
    if outline:
        pen = cv.pen(key + "tube")
        pen.line(left, w=lw, amp=0.5)
        pen.line(right, w=lw * 0.8, amp=0.5)
        if ends:
            pen.line([left[-1], right[-1]], w=lw * 0.8, amp=0.4)
    return poly


def rounded_rect(cx, cy, w, h, r, angle=0.0, n=8):
    pts = []
    for (qx, qy, a0) in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for a in np.linspace(math.radians(a0), math.radians(a0 + 90), n):
            pts.append((qx + r * math.cos(a), qy + r * math.sin(a)))
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def draw_phone(cv, key, cx, cy, w, h, angle=0.0, turn=0.0, screen=None, glow=0.0, prog=1.0):
    """A phone at (cx, cy), w x h, tilted by angle (deg); turn (deg) spins it about its long axis:
    0 its screen to us, 180 its back. screen(cv, frame) draws on its screen (a world rectangle, its corners)."""
    k = math.cos(math.radians(turn))
    ww = max(6.0, abs(k) * w)
    body = rounded_rect(cx, cy, ww, h, min(ww / 2 - 1, w * 0.16), angle)
    cv.solid(body)
    pen = cv.pen(key + "phone")
    if glow > 0 and k > 0:  # its light, scratched out around it
        g = cv.pen(key + "glow")
        for a in np.linspace(0, 2 * math.pi, 70, endpoint=False):
            a += g.rng.uniform(-0.03, 0.03)
            r0 = 1.08
            r1 = r0 + glow * g.rng.uniform(0.18, 0.45)
            ca, sa = math.cos(a), math.sin(a)
            g.line([(cx + ww * 0.5 * r0 * ca * 1.05, cy + h * 0.5 * r0 * sa), (cx + ww * 0.5 * r1 * ca * 1.25, cy + h * 0.5 * r1 * sa)], w=1.3, amp=0.3)
        cv.solid(body)
    pen.line(body + body[:1], w=4.2, amp=0.5)
    if abs(k) < 0.15:
        return body
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def P(x, y):  # phone units (x across its face, -1..1; y along, -1..1) -> world
        x = x * ww / 2
        y = y * h / 2
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)
    if k > 0:  # its screen
        bez_ = 0.075
        scr = rounded_rect(cx, cy, ww * (1 - bez_ * 2), h * (1 - bez_ * 1.0), min(ww, w) * 0.11, angle)
        pen.line(scr + scr[:1], w=1.8, amp=0.4)
        pen.line([P(-0.18, -0.93), P(0.18, -0.93)], w=3.0, amp=0.3)  # the speaker
        if screen is not None:
            screen(cv, dict(P=P, k=k, w=ww, h=h, angle=angle, poly=scr))
    else:  # its back: the cameras in their block
        blk = rounded_rect(*P(-0.45, -0.72), ww * 0.42, h * 0.2, ww * 0.07, angle)
        pen.line(blk + blk[:1], w=2.2, amp=0.4)
        for (x, y) in ((-0.58, -0.8), (-0.58, -0.64), (-0.32, -0.72)):
            cxx, cyy = P(x, y)
            r = ww * 0.065
            pen.line([(cxx + r * math.cos(t), cyy + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 18)], w=1.8, amp=0.3)
        ink.hatch(cv.white, [body], ink.flat(0.45), cv.rng(key + "back"), angle=angle + 60, gap=7.0, lo=0.3, wmax=1.6, cross=0)
        pen.line(body + body[:1], w=4.2, amp=0.5)
    return body


# --- hands
def _dir(a):
    return np.array([math.cos(a), math.sin(a)])


def finger(cv, key, base, ang, lengths, widths, curls, gap, prog=1.0, gain=1.0, lw=2.2):
    """A finger from its base along angle ang (rad), its joints bending by curls (rad): drawn as a tube
    with a round tip. Returns its polygon and its tip."""
    pts = [np.asarray(base, float)]
    a = ang
    for Lseg, cu in zip(lengths, curls):
        a += cu
        pts.append(pts[-1] + Lseg * _dir(a))
    left, right = ink.limb([tuple(q) for q in pts], widths, n=4)
    tip = pts[-1]
    r = widths[-1] / 2
    d = _dir(a)
    nrm = np.array([-d[1], d[0]])
    cap = [tuple(tip + r * (math.cos(t) * nrm + math.sin(t) * d)) for t in np.linspace(0, math.pi, 9)]
    poly = left + cap[::-1][1:-1] + right[::-1] if False else left + [cap[i] for i in range(8, -1, -1)][1:-1] + right[::-1]
    cv.solid(poly)
    rr = tube_rings(left, right, lambda n: lit(n) * gain, gap, bulge=0.3, n=7)
    ink.engrave(cv.white, rr, clip=[poly], lo=0.3, hi=0.95, wmax=1.8, prog=prog, rng=cv.rng(key + "fr"))
    pen = cv.pen(key + "finger")
    pen.line(poly + poly[:1], w=lw, amp=0.35)
    for q, w in zip(pts[1:-1], widths[1:-1]):  # the knuckles' creases
        pen.line([tuple(q + nrm * w * 0.25), tuple(q - nrm * w * 0.25 + d * 1.5)], w=lw * 0.6, amp=0.2)
    return poly, tip


def hand_open(cv, key, wrist, ang, L, side, spread=1.0, curl=0.0, gap=5.0, prog=1.0):
    """A hand seen from its palm: wrist at `wrist`, pointing along ang (deg), L long (world px); side +1 if
    its thumb is on the viewer's right of the hand's axis."""
    a = math.radians(ang)
    u, v = _dir(a), _dir(a + side * math.pi / 2)  # along the hand, toward the thumb
    W0 = np.asarray(wrist, float)

    def at(pu, pv):
        return W0 + u * pu * L + v * pv * L
    palm = [at(0.0, -0.16), at(0.06, -0.2), at(0.5, -0.22), at(0.58, -0.17), at(0.6, 0.0), at(0.57, 0.17), at(0.45, 0.24),
            at(0.2, 0.22), at(0.0, 0.17)]
    palm = ink.smooth([tuple(q) for q in palm], closed=True, n=4)
    # fingers behind the palm's edge first, so the palm covers their roots
    fingers = [(0.17, 0.43, 0.105, 0.10), (0.055, 0.47, 0.11, 0.02), (-0.06, 0.44, 0.105, -0.08), (-0.165, 0.35, 0.09, -0.18)]
    for k, (fv, fl, fw, fa) in enumerate(fingers):
        base = at(0.52, fv)
        fang = a + side * fa * spread
        segs = [fl * 0.45 * L, fl * 0.3 * L, fl * 0.25 * L]
        cu = [-side * 0.0, side * 0.35 * curl, side * 0.45 * curl]
        finger(cv, key + f"f{k}", base, fang, segs, [fw * L, fw * L * 0.95, fw * L * 0.85, fw * L * 0.78], cu, gap, prog)
    cv.solid(palm)
    light = ink.sphere(*at(0.3, 0.0), L * 0.4, L * 0.4, amb=0.08)
    ink.hatch(cv.white, [palm], light, cv.rng(key + "palm"), angle=ang + 70, gap=gap * 1.05, lo=0.3, wmax=2.0, cross=0.8)
    pen = cv.pen(key + "palm")
    pen.line(palm + palm[:1], w=2.4, amp=0.4)
    pen.line(ink.smooth([tuple(at(0.42, -0.2)), tuple(at(0.36, 0.0)), tuple(at(0.4, 0.18))], n=5), w=1.4, amp=0.3)  # the palm's lines
    pen.line(ink.smooth([tuple(at(0.12, 0.12)), tuple(at(0.3, 0.06)), tuple(at(0.46, 0.1))], n=5), w=1.3, amp=0.3)
    # the thumb, over the palm's side
    tb = at(0.14, 0.2)
    finger(cv, key + "th", tb, a + side * (0.9 - 0.5 * curl), [0.2 * L, 0.17 * L], [0.13 * L, 0.115 * L, 0.1 * L], [0, -side * 0.35], gap, prog)
    return palm


# --- Tony, whole
def tony_pose(**k):
    """A pose with its defaults: neck base (x, y), scale s; the body's lean (deg), shrug, breath; the head's
    turn (yaw, pitch, roll) and its expression; each arm's wrist (world) and hand; the phone."""
    p = dict(x=540.0, y=1010.0, s=1.6, lean=0.0, shrug=0.0, breath=0.0, yaw=0.0, pitch=0.0, roll=0.0, hdx=0.0, hdy=0.0,
             ex={}, arm_r=None, arm_l=None, phone=None, lift=0.0, face=TONY, head_k=HEAD_K, build=1.0, outfit="tee", cloth=1.0)
    p.update(k)
    return p


def body_point(P, x, y):
    """A point of the torso (body units from the neck base), leaning with it about the hips."""
    s = P["s"]
    a = math.radians(P["lean"])
    px, py = 0.0, 700.0  # the hips
    dx, dy = x - px, y - py
    rx, ry = px + dx * math.cos(a) - dy * math.sin(a), py + dx * math.sin(a) + dy * math.cos(a)
    return np.array([P["x"] + rx * s, P["y"] + (ry - 0.0) * s])


def hand_point(cv, key, wrist, ang, L, side, gap=5.0, prog=1.0, index=True):
    """A fist, the index finger out (pointing along ang, deg) or folded too."""
    a = math.radians(ang)
    u, v = _dir(a), _dir(a + side * math.pi / 2)
    W0 = np.asarray(wrist, float)

    def at(pu, pv):
        return W0 + u * pu * L + v * pv * L
    fist = ink.smooth([tuple(at(0.0, -0.17)), tuple(at(0.3, -0.24)), tuple(at(0.55, -0.2)), tuple(at(0.62, 0.0)), tuple(at(0.55, 0.2)),
                       tuple(at(0.25, 0.22)), tuple(at(0.0, 0.16))], closed=True, n=5)
    cv.solid(fist)
    light = ink.sphere(*at(0.3, 0.0), L * 0.35, L * 0.35, amb=0.08)
    ink.hatch(cv.white, [fist], light, cv.rng(key + "fist"), angle=ang + 70, gap=gap, lo=0.3, wmax=1.9, cross=0.8)
    pen = cv.pen(key + "fist")
    pen.line(fist + fist[:1], w=2.4, amp=0.4)
    for k in range(3 if index else 4):  # the folded fingers' knuckles
        q0, q1 = at(0.42 + 0.03 * k, -0.18 + 0.12 * k + (0.12 if index else 0)), at(0.58, -0.14 + 0.12 * k + (0.12 if index else 0))
        pen.line([tuple(q0), tuple(q1)], w=1.4, amp=0.3)
    if index:
        finger(cv, key + "idx", at(0.5, 0.12), a + side * 0.05, [0.22 * L, 0.15 * L, 0.12 * L], [0.1 * L, 0.095 * L, 0.088 * L, 0.08 * L],
               [0, 0, 0], gap, prog)
    finger(cv, key + "th", at(0.2, 0.2), a + side * 0.6, [0.17 * L, 0.14 * L], [0.12 * L, 0.11 * L, 0.1 * L], [0, -side * 0.5], gap, prog)


def thumb_on_edge(cv, key, edge_pt, toward, L, side, gap, prog=1.0):
    """A thumb pressed on a phone's edge, from behind it: its root at edge_pt, pointing along toward (rad)."""
    finger(cv, key, edge_pt, toward, [0.16 * L, 0.13 * L], [0.135 * L, 0.125 * L, 0.11 * L], [0.0, side * 0.25], gap, prog)


def fingertips_on_edge(cv, key, pts, ang, L, gap, prog=1.0):
    """Fingertips curling round a phone's edge from behind it: short rounded ends, one at each point."""
    for k, q in enumerate(pts):
        wk = (0.1, 0.105, 0.1, 0.085)[k % 4] * L
        base = np.asarray(q, float) - _dir(ang) * wk * 0.2
        poly, tip = finger(cv, key + f"t{k}", base, ang, [wk * 0.55], [wk, wk * 0.94], [0.0], gap * 2, prog, gain=0.9)
        nrm = _dir(ang + math.pi / 2)
        nail = [tuple(tip - _dir(ang) * wk * 0.42 + nrm * wk * 0.22), tuple(tip - _dir(ang) * wk * 0.12 + nrm * wk * 0.18),
                tuple(tip - _dir(ang) * wk * 0.12 - nrm * wk * 0.18), tuple(tip - _dir(ang) * wk * 0.42 - nrm * wk * 0.22)]
        cv.pen(key + f"n{k}").line(nail, w=1.2, amp=0.2)


# --- Tony, whole
HEAD_K = 1.15  # his head, a little big for his body: a cartoon's


def tony_pose(**k):
    """A pose with its defaults: neck base (x, y), scale s; the body's lean (deg), shrug, breath; the head's
    turn (yaw, pitch, roll) and its expression; each arm's wrist (world) and hand; the phone."""
    p = dict(x=540.0, y=1010.0, s=1.6, lean=0.0, shrug=0.0, breath=0.0, yaw=0.0, pitch=0.0, roll=0.0, hdx=0.0, hdy=0.0,
             ex={}, arm_r=None, arm_l=None, phone=None, lift=0.0, face=TONY, head_k=HEAD_K, build=1.0, outfit="tee", cloth=1.0)
    p.update(k)
    return p


def body_point(P, x, y):
    """A point of the torso (body units from the neck base), leaning with it about the hips."""
    s = P["s"]
    a = math.radians(P["lean"])
    px, py = 0.0, 620.0  # the hips
    dx, dy = x - px, y - py
    return np.array([P["x"] + (px + dx * math.cos(a) - dy * math.sin(a)) * s, P["y"] + (py + dx * math.sin(a) + dy * math.cos(a)) * s])


def head_of(P):
    s, f, hk = P["s"], P["face"], P["head_k"]
    hc = body_point(P, P["hdx"], P["hdy"] - (f["b"] * hk + 22))
    return Head(hc[0], hc[1], s * hk, P["yaw"], P["pitch"], P["roll"] + P["lean"] * 0.6, a=f["a"], b=f["b"], c=f["c"], shape=f["shape"])


def draw_arm(cv, key, P, side, arm, gap, prog):
    """An arm: the upper arm in its sleeve, the forearm bare, the hand."""
    s = P["s"]
    bd = P["build"]
    up = P["breath"] * 4 + P["shrug"] * 20
    sh = body_point(P, side * 138 * bd, 58 - up)
    l1, l2 = 228 * s * arm.get("k1", 1.0) * bd ** 0.5, 205 * s * arm.get("k2", 1.0) * bd ** 0.5  # k: a bone pointing at us looks shorter
    s = s * bd ** 0.6
    el, wr = ik(sh, arm["wrist"], l1, l2, arm.get("elbow", (side * 0.6, 1.0)))
    pen = cv.pen(key + "arm")
    mid_e = (sh + el) / 2 + np.array([side * 4 * s, 0])
    upper = [tuple(sh), tuple(mid_e), tuple(el)]
    mid_f = (el + wr) / 2
    fore = [tuple(el), tuple(mid_f + (mid_f - el) * 0.0), tuple(wr)]
    if arm.get("hand") == "pocket":
        pk = [tuple(body_point(P, side * 136, 600)), tuple(body_point(P, side * 104, 610)), tuple(body_point(P, side * 72, 622))]
    left, right = ink.limb(fore, [50 * s, 47 * s, 38 * s], n=6)
    fpoly = left + right[::-1]
    cv.solid(fpoly)
    ink.engrave(cv.white, tube_along(left, right, lambda n: lit(n), gap * 1.05), clip=[fpoly], lo=0.34, wmax=2.0, prog=prog,
                rng=cv.rng(key + "fr"))
    pen.line(left, w=2.4, amp=0.5)
    pen.line(right, w=1.9, amp=0.5)
    if arm.get("hand") == "pocket":
        pen.line(pk, w=2.6, amp=0.5)
    # the upper arm, in the sleeve to below the shoulder, then bare to the elbow
    left, right = ink.limb(upper, [64 * s, 58 * s, 50 * s], n=6)
    upoly = left + right[::-1]
    cv.solid(upoly)
    ink.engrave(cv.white, tube_along(left, right, lambda n: lit(n), gap * 1.05), clip=[upoly], lo=0.34, wmax=2.0, prog=prog,
                rng=cv.rng(key + "ur"))
    pen.line(left, w=2.2, amp=0.5)
    pen.line(right, w=1.8, amp=0.5)
    sl_end = sh + (el - sh) * 0.5
    sleeve = [tuple(sh - (el - sh) * 0.06), tuple((sh + sl_end) / 2), tuple(sl_end)]
    left, right = ink.limb(sleeve, [82 * s, 80 * s, 76 * s], n=5)
    spoly = left + right[::-1]
    cv.solid(spoly)
    ink.engrave(cv.white, tube_along(left, right, lambda n: lit(n) * 0.62, gap * 1.2), clip=[spoly], lo=0.4, wmax=1.5, prog=prog)
    pen.line(left, w=2.4, amp=0.5)
    pen.line(right, w=2.0, amp=0.5)
    hem = ink.smooth([left[-1], tuple((np.asarray(left[-1]) + np.asarray(right[-1])) / 2 + (el - sh) / np.hypot(*(el - sh)) * 6 * s), right[-1]], n=4)
    pen.line(hem, w=2.6, amp=0.4)
    fold = [tuple(np.asarray(left[2]) * 0.7 + np.asarray(right[3]) * 0.3), tuple(np.asarray(left[3]) * 0.45 + np.asarray(right[4]) * 0.55)]
    pen.line(fold, w=1.4, amp=0.4)
    hand = arm.get("hand")
    if hand == "open":
        hand_open(cv, key + "h", wr, arm.get("ang", -90), 150 * s, arm.get("thumb", -side), arm.get("spread", 1.0), arm.get("curl", 0.0),
                  gap * 0.85, prog)
    elif hand == "point":
        hand_point(cv, key + "h", wr, arm.get("ang", 0), 150 * s, arm.get("thumb", -side), gap * 0.85, prog)
    elif hand == "fist":
        hand_point(cv, key + "h", wr, arm.get("ang", 90), 150 * s, arm.get("thumb", -side), gap * 0.85, prog, index=False)
    return el, wr


def draw_tony(cv, key, P, prog=1.0, screen=None, parts=("body", "head", "arms")):
    """Tony, or anyone: the pose says whose face, how big a head, what build and clothes. parts: what to
    draw now (a child behind his desk: his body and head, then the desk, then his arms on it)."""
    s = P["s"]
    bd = P["build"]
    zc = dt.CAM[0]
    gap = 6.0 / zc
    pen = cv.pen(key + "body")
    up = P["breath"] * 4 + P["shrug"] * 20

    def B(x, y):
        return body_point(P, x, y)

    out = dict(head=head_of(P), lens=[])
    if "body" not in parts:
        if "arms" in parts:
            for side, name in ((1, "arm_l"), (-1, "arm_r")):
                if P[name] is not None:
                    out[name] = draw_arm(cv, key + name, P, side, P[name], gap, prog)
        return out
    # --- the neck, behind the collar and the beard
    nw = s * bd ** 0.5
    tube(cv, key + "neck", [tuple(B(P["hdx"] * 0.5, -70)), tuple(B(P["hdx"] * 0.2, -30)), tuple(B(0, 10))], [84 * nw, 88 * nw, 94 * nw], gap * 1.3,
         prog, gain=0.5 if P["face"]["beard"] else 0.8, lw=1.8, ends=False, lo=0.35)

    # --- the torso: a dark tee
    shy = 8 * P["shrug"]
    L_side = [(-54, -4), (-104, 10 - up * 0.7), (-150 + shy, 34 - up), (-166 + shy, 76 - up * 0.6), (-158, 140), (-146, 240), (-138, 420), (-136, 760)]
    L_side = [(x * (bd if i > 0 else bd ** 0.5), y) for i, (x, y) in enumerate(L_side)]
    R_side = [(-x, y) for x, y in L_side]
    torso = [tuple(B(x, y)) for x, y in ink.smooth(L_side, n=5)] + [tuple(B(x, y)) for x, y in ink.smooth(R_side, n=5)[::-1]]
    cv.solid(torso)
    sh_l = B(-120, 60)
    light = ink.add(ink.scale(ink.glow_at(*sh_l, 190 * s, 1.0), 0.75 * P["cloth"]), ink.flat(0.05))
    ink.hatch(cv.white, [torso], light, cv.rng(key + "tee"), angle=58 + P["lean"], gap=gap * 1.1, lo=0.42, hi=0.9, wmax=1.7, cross=0, prog=prog)
    for (x0, y0, x1, y1, x2, y2) in ((-140, 170, -96, 290, -74, 420), (140, 175, 100, 285, 84, 410), (-112, 500, -44, 540, 24, 528),
                                     (-58, 110, -36, 160, -44, 220), (40, 300, 60, 380, 52, 470)):
        pen.line([tuple(B(x, y)) for x, y in ink.smooth([(x0, y0), (x1, y1), (x2, y2)], n=6)], w=1.6, amp=0.8)
    n2 = len(torso) // 2
    pen.line(torso[:n2], w=2.6, amp=0.6)
    pen.line(torso[n2:], w=2.0, amp=0.6)
    if P["outfit"] == "shirt":  # a shirt's collar, a tie
        for side in (-1, 1):
            col = [tuple(B(side * 10, 8)), tuple(B(side * 62, -6)), tuple(B(side * 70, 40)), tuple(B(side * 22, 56))]
            cv.solid(col)
            pen.line(col + col[:1], w=2.2, amp=0.4)
        tie = [tuple(B(-14, 30)), tuple(B(14, 30)), tuple(B(22, 300)), tuple(B(0, 330)), tuple(B(-22, 300))]
        cv.solid(tie)
        ink.hatch(cv.white, [tie], ink.flat(0.6), cv.rng(key + "tie"), angle=40, gap=gap * 1.2, lo=0.3, wmax=1.6, cross=0)
        pen.line(tie + tie[:1], w=2.2, amp=0.4)
        for y in (180, 300, 420):
            cv.disc(*B(0, y + 20), 4 * s)
    th = np.linspace(0, math.pi, 24)  # the collar: a ribbed band round the neck
    if P["outfit"] != "shirt":
        outer = [tuple(B(58 * bd ** 0.5 * math.cos(t), 2 + 22 * math.sin(t))) for t in th]
        inner = [tuple(B(44 * bd ** 0.5 * math.cos(t), 0 + 13 * math.sin(t))) for t in th[::-1]]
        band = outer + inner
        cv.solid(band)
        ink.hatch(cv.white, [band], ink.flat(0.55), cv.rng(key + "rib"), angle=95 + P["lean"], gap=gap * 0.85, lo=0.3, wmax=1.4, cross=0)
        pen.line(outer, w=2.4, amp=0.4)
        pen.line(inner[::-1], w=1.8, amp=0.4)

    # --- the head
    if "head" not in parts:
        return out
    hd = head_of(P)
    lift = None
    if P["lift"] > 0:
        k_l = P["lift"]
        dirl = norm(np.array([0.0, 0.85, 0.55]))
        lift = lambda n, p: k_l * 0.7 * np.clip(n @ dirl, 0, 1) ** 1.5
    info = draw_head(cv, key, hd, P["face"], P["ex"], prog=prog, lift=lift)

    # --- the arms (behind the phone), the phone, the hand round it
    out = dict(head=hd, lens=info["lens"])
    if "arms" not in parts:
        return out
    for side, name in ((1, "arm_l"), (-1, "arm_r")):
        if P[name] is not None:
            out[name] = draw_arm(cv, key + name, P, side, P[name], gap, prog)
    ph = P.get("phone")
    if ph is not None:
        k = math.cos(math.radians(ph.get("turn", 0)))
        draw_phone(cv, key + "ph", ph["cx"], ph["cy"], ph["w"], ph["h"], ph.get("angle", 0), ph.get("turn", 0), screen, ph.get("glow", 0), prog)
        a = math.radians(ph.get("angle", 0))
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = -math.sin(a), math.cos(a)
        ww = max(6.0, abs(k) * ph["w"])

        def Q(x, y):
            return np.array([ph["cx"] + x * ww / 2 * ux + y * ph["h"] / 2 * vx, ph["cy"] + x * ww / 2 * uy + y * ph["h"] / 2 * vy])
        L = 150 * s
        if k > 0.15:  # its screen to us: his right hand behind it, fingertips round our left edge, the thumb on the right one
            fingertips_on_edge(cv, key + "ft", [Q(-1.0, 0.16 + 0.2 * i) for i in range(3)], a, L * 1.25, gap, prog)
            thumb_on_edge(cv, key + "th", Q(1.0, 0.62) + np.array([ux, uy]) * 16 * s, a + math.pi + 0.75, L * 1.2, 1, gap, prog)
        elif k < -0.15:  # its back to us: his fingers across it
            for i in range(3):
                q = Q(-1.06, 0.3 + 0.2 * i)
                finger(cv, key + f"bf{i}", q, a + 0.05 * i, [ww * 0.34, ww * 0.22], [L * 0.12, L * 0.115, L * 0.1], [0.0, 0.25], gap * 1.5, prog, gain=0.95)
    return out


def draw_shadow(cv, key, x, y, s, prog=1.0, rim_side=-1, rise=1.0):
    """Someone close, as a looming shadow: a black figure, only its edge caught by a light (on rim_side);
    rise: how far it has risen from below (0..1)."""
    y = y + (1 - rise) * 900 * s
    pen = cv.pen(key + "shadow")
    head = [(x + 92 * s * math.cos(t), y - 190 * s + 112 * s * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48)]
    body = ink.smooth([(x - 64 * s, y - 70 * s), (x - 190 * s, y - 20 * s), (x - 252 * s, y + 110 * s), (x - 274 * s, y + 900 * s),
                       (x + 274 * s, y + 900 * s), (x + 252 * s, y + 110 * s), (x + 190 * s, y - 20 * s), (x + 64 * s, y - 70 * s)], n=6)
    neck = [(x - 52 * s, y - 120 * s), (x + 52 * s, y - 120 * s), (x + 64 * s, y - 50 * s), (x - 64 * s, y - 50 * s)]
    shapes = [body, neck, head]
    for sh in shapes:
        cv.solid(sh)
    # its lit edge: the figure hatched, then covered again by itself a little shifted away from the light
    rng = cv.rng(key + "sh")
    ink.hatch(cv.white, shapes, ink.flat(0.75), rng, angle=62 * -rim_side, gap=6.2 / dt.CAM[0], lo=0.3, wmax=1.9, cross=0, prog=prog)
    off = -rim_side * 26 * s
    for sh in shapes:
        cv.solid([(px + off, py + 8 * s) for px, py in sh])
    pen.line(head + head[:1], w=2.2, amp=0.6)
    pen.line(body, w=2.2, amp=0.6)
