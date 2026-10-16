"""The engraving kit: what makes the drawings read as scratchboard rather than as lines.

- light: shapes get a form (a sphere, a cylinder, a flat), the scene a light; each point of a shape gets how
  lit it is (Lambert, plus a little ambient);
- hatch: white strokes scratched across a shape, as many and as heavy as the light there (a second direction
  where it is brightest), in screen space so they keep their spacing whatever the camera;
- engrave: strokes that follow a form (rings around a head, an arm), each as wide as the light along it;
- stipple: dots for the beard, as dense as the light;
- solid: a shape filled black first, so what is behind it is hidden (the drawing has depth);
- smooth: Catmull-Rom curves through a few points; limb: a tube along a bone chain.
Everything goes through draw_test's camera (draw_test.CAM), and works on the box around the shape only.
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import draw_test as dt

W, H, S = 1080, 1920, dt.S
LIGHT = np.array([-0.55, -0.62, 0.56])  # the key light: from the upper left, a little in front
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def to_screen(pts):
    a = np.asarray(pts, float).reshape(-1, 2)
    z, px, py, qx, qy = dt.CAM
    return np.stack([qx + (a[:, 0] - px) * z, qy + (a[:, 1] - py) * z], 1)


def to_world(xs, ys):
    z, px, py, qx, qy = dt.CAM
    return px + (xs - qx) / z, py + (ys - qy) / z


def smooth(pts, closed=False, n=8):
    """A Catmull-Rom curve through the points."""
    p = np.asarray(pts, float).reshape(-1, 2)
    if len(p) < 3:
        return p.tolist()
    p = np.vstack([p[-1:], p, p[:2]]) if closed else np.vstack([p[:1], p, p[-1:]])
    t = np.linspace(0, 1, n, endpoint=False)[:, None]
    t2, t3 = t * t, t * t * t
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-2:-1])
    return np.vstack(out).tolist()


def box(screen_polys, pad=6):
    """The pixel box around screen points, inside the frame; None when it is off the frame."""
    xs = np.concatenate([np.asarray(p)[:, 0] for p in screen_polys if len(p)])
    ys = np.concatenate([np.asarray(p)[:, 1] for p in screen_polys if len(p)])
    x0, x1 = max(0, int(xs.min()) - pad), min(W, int(xs.max()) + pad + 1)
    y0, y1 = max(0, int(ys.min()) - pad), min(H, int(ys.max()) + pad + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def local_mask(screen_polys, b, evenodd=False):
    x0, y0, x1, y1 = b
    m = Image.new("1", ((x1 - x0) * S, (y1 - y0) * S), 0)
    for sp in screen_polys:
        pts = [((x - x0) * S, (y - y0) * S) for x, y in sp]
        if len(pts) < 3:
            continue
        if evenodd:
            t = Image.new("1", m.size, 0)
            ImageDraw.Draw(t).polygon(pts, fill=1)
            m = ImageChops.logical_xor(m, t)
        else:
            ImageDraw.Draw(m).polygon(pts, fill=1)
    return m.convert("L")


def lighten_into(img, layer, mask, b):
    """Scratch a local layer into the drawing, inside the mask."""
    x0, y0 = b[0] * S, b[1] * S
    region = img.crop((x0, y0, x0 + layer.width, y0 + layer.height))
    ink_ = layer if mask is None else ImageChops.multiply(layer, mask)
    img.paste(ImageChops.lighter(region, ink_), (x0, y0))


def solid(img, poly, fill=0):
    """The shape, filled (black by default) through the camera: it hides what was drawn behind it."""
    pts = [(x * S, y * S) for x, y in to_screen(poly)]
    if len(pts) > 2:
        ImageDraw.Draw(img).polygon(pts, fill=fill)


def mask_of(polys, evenodd=False):
    m = Image.new("1", (W * S, H * S), 0)
    for poly in polys:
        pts = [(x * S, y * S) for x, y in to_screen(poly)]
        if len(pts) < 3:
            continue
        if evenodd:
            t = Image.new("1", (W * S, H * S), 0)
            ImageDraw.Draw(t).polygon(pts, fill=1)
            m = ImageChops.logical_xor(m, t)
        else:
            ImageDraw.Draw(m).polygon(pts, fill=1)
    return m.convert("L")


# --- forms: how lit each point of a shape is
def sphere(cx, cy, rx, ry, amb=0.12, gain=1.0, light=LIGHT):
    def f(x, y):
        nx, ny = (x - cx) / rx, (y - cy) / ry
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
        lam = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
        return np.clip(amb + gain * lam, 0, 1)
    return f


def cylinder(x0, y0, x1, y1, r, amb=0.1, gain=1.0, light=LIGHT):
    """A tube along (x0, y0)-(x1, y1), of radius r."""
    ax, ay = x1 - x0, y1 - y0
    la = math.hypot(ax, ay) or 1.0
    ux, uy = ax / la, ay / la

    def f(x, y):
        d = ((x - x0) * -uy + (y - y0) * ux) / r
        n_across = np.clip(d, -1, 1)
        nz = np.sqrt(np.clip(1 - n_across ** 2, 0, 1))
        nx, ny = n_across * -uy, n_across * ux
        lam = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
        return np.clip(amb + gain * lam, 0, 1)
    return f


def flat(level):
    def f(x, y):
        return np.full_like(np.asarray(x, float), level, dtype=float)
    return f


def glow_at(gx, gy, radius, power=1.0):
    """A local light (a phone, a lamp): 1 at its centre, falling off."""
    def f(x, y):
        d2 = ((x - gx) ** 2 + (y - gy) ** 2) / (radius * radius)
        return np.clip(power / (1 + d2), 0, 1)
    return f


def add(*fs):
    def f(x, y):
        out = 0
        for g in fs:
            out = out + g(x, y)
        return np.clip(out, 0, 1)
    return f


def scale(fn, k):
    return lambda x, y: np.clip(fn(x, y) * k, 0, 1)


# --- the strokes
def _segments(d, P, I, lo, hi, wmax, fill, jit=None):
    """A polyline drawn as runs of segments, each run as wide as the light (none where it is below lo)."""
    n = len(P)
    if n < 2:
        return
    Im = (I[:-1] + I[1:]) / 2
    q = np.clip((Im - lo) / max(hi - lo, 1e-3), 0, 1)
    wq = np.round(np.where(Im >= lo, np.maximum(0.15, q) * wmax * S, 0) * 2) / 2
    i = 0
    while i < n - 1:
        if wq[i] <= 0:
            i += 1
            continue
        j = i
        while j < n - 1 and wq[j] == wq[i] and j - i < 6:
            j += 1
        pts = [(float(P[k, 0]), float(P[k, 1])) for k in range(i, j + 1)]
        w = max(1, int(round(wq[i])))
        d.line(pts, fill=fill, width=w, joint="curve")
        if w >= 3:
            r = w / 2
            x, y = pts[0]
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
        i = j


def hatch(img, polys, light, rng, angle=45, gap=7.5, lo=0.32, hi=0.95, wmax=2.8, cross=0.72, prog=1.0, evenodd=False,
          curve=0.0, fill=255):
    """White strokes across the shapes, as dense and as heavy as the light; a second direction where it is
    brightest (cross); `curve` bends them a little, like an engraver following a form. Screen-spaced."""
    if prog <= 0:
        return
    sp = [to_screen(p) for p in polys if len(p) > 2]
    if not sp:
        return
    b = box(sp)
    if b is None:
        return
    bx0, by0, bx1, by1 = b
    layer = Image.new("L", ((bx1 - bx0) * S, (by1 - by0) * S), 0)
    d = ImageDraw.Draw(layer)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    R = math.hypot(bx1 - bx0, by1 - by0) / 2 + 4
    passes = [(angle, lo)] + ([(angle + 68, max(lo, cross))] if cross else [])
    tt = np.arange(-R, R, 3.0)
    for ang, low in passes:
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        offs = np.arange(-R, R, gap) + rng.uniform(0, gap)
        n_on = int(len(offs) * min(1.0, prog))
        for o in offs[:n_on]:
            bend = curve * (tt / R) ** 2 * gap * 3
            X = cx + nx * (o + bend) + dx * tt
            Y = cy + ny * (o + bend) + dy * tt
            ins = (X > bx0 - 2) & (X < bx1 + 2) & (Y > by0 - 2) & (Y < by1 + 2)
            if not ins.any():
                continue
            X, Y = X[ins], Y[ins]
            wx, wy = to_world(X, Y)
            I = light(wx, wy) + rng.uniform(-0.03, 0.03)
            if not (I > low).any():
                continue
            jit = rng.normal(0, 0.45, (len(X), 2))
            P = np.stack([(X + jit[:, 0] - bx0) * S, (Y + jit[:, 1] - by0) * S], 1)
            _segments(d, P, I, low, hi, wmax * dt.ink() ** 0.5, fill)
    lighten_into(img, layer, local_mask(sp, b, evenodd), b)


def engrave(img, lines, clip=None, lo=0.3, hi=0.95, wmax=2.6, prog=1.0, fill=255, rng=None, evenodd=False):
    """Strokes that follow a form: each (world points, light along them), as wide as the light;
    kept inside `clip` (world polygons) when given."""
    if prog <= 0 or not lines:
        return
    n_on = max(1, int(round(len(lines) * min(1.0, prog))))
    sl = [(to_screen(p), np.asarray(I, float)) for p, I in lines[:n_on] if len(p) > 1]
    if not sl:
        return
    cl = [to_screen(c) for c in clip if len(c) > 2] if clip else None
    b = box(cl if cl else [p for p, _ in sl])
    if b is None:
        return
    bx0, by0, bx1, by1 = b
    layer = Image.new("L", ((bx1 - bx0) * S, (by1 - by0) * S), 0)
    d = ImageDraw.Draw(layer)
    for P, I in sl:
        if rng is not None:
            P = P + rng.normal(0, 0.35, P.shape)
        Q = np.stack([(P[:, 0] - bx0) * S, (P[:, 1] - by0) * S], 1)
        _segments(d, Q, I, lo, hi, wmax * dt.ink() ** 0.5, fill)
    lighten_into(img, layer, local_mask(cl, b, evenodd) if cl else None, b)


def stipple(img, polys, light, rng, density=0.012, lo=0.25, r=1.2, prog=1.0):
    """Dots where the light falls (the beard's texture), more where it is brighter."""
    if prog <= 0:
        return
    sp = [to_screen(p) for p in polys if len(p) > 2]
    b = box(sp, pad=2) if sp else None
    if b is None:
        return
    bx0, by0, bx1, by1 = b
    n = int((bx1 - bx0) * (by1 - by0) * density * prog)
    if n <= 0:
        return
    X = rng.uniform(bx0, bx1, n)
    Y = rng.uniform(by0, by1, n)
    wx, wy = to_world(X, Y)
    I = light(wx, wy)
    keep = rng.random(n) < np.clip((I - lo) / (1 - lo), 0, 1)
    layer = Image.new("L", ((bx1 - bx0) * S, (by1 - by0) * S), 0)
    d = ImageDraw.Draw(layer)
    rr0 = r * S * dt.ink() ** 0.5
    for x, y, rr in zip(X[keep], Y[keep], rng.uniform(0.7, 1.3, int(keep.sum())) * rr0):
        x, y = (x - bx0) * S, (y - by0) * S
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=255)
    lighten_into(img, layer, local_mask(sp, b), b)


def limb(chain, widths, n=6):
    """A tube's outline along a chain of joints, with a width at each joint."""
    pts = smooth(chain, n=n)
    ws = np.interp(np.linspace(0, 1, len(pts)), np.linspace(0, 1, len(widths)), widths)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        tl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / tl, tx / tl
        left.append((x + nx * ws[i] / 2, y + ny * ws[i] / 2))
        right.append((x - nx * ws[i] / 2, y - ny * ws[i] / 2))
    return left, right


def rot(pts, cx, cy, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]
