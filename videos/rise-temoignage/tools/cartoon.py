"""Characters drawn flat, the way Tony's first drawing was (draw_test.py): a caricature in wobbly white lines, a
few straight hatchings, the grain of chalk; posed again for every drawing.

A head is flat: when it turns, its features slide across it (and the far ear goes); when it nods, they go up
or down; it tilts as a whole. Eyes blink and look about, brows rise or knit, the mouth smiles or opens.
A body is a contour and its folds; arms are two lines each (bent at the elbow), hands are outlines.
Poses are the same as tools/rig.py's (tony_pose), so an animation can be drawn in either style.
"""
import math

import numpy as np
from PIL import Image, ImageFilter

import draw_test as dt
import ink
import rig
from draw_test import arc, bez
from rig import Canvas, body_point, clip01, ik, lerp

W, H, S = 1080, 1920, dt.S


# --- faces: head units are draw_test's (a jaw 165 x 190 round the head's centre); unit: head units -> body units
TONY = dict(A=165, B=190, unit=108 / 190, eyes=66, eye_y=-26, eye_k=1.0, glasses=(58, 52), hair="slick", beard=True, moustache=True,
            nose="tony", mouth_w=44, droop=0.38, bags=True, lashes=False, freckles=False)
KID = dict(TONY, A=150, B=168, unit=100 / 168, eyes=58, eye_y=-14, eye_k=1.12, glasses=(50, 46), hair="bowl", beard=False, moustache=False,
           nose="small", mouth_w=30, droop=0.25, bags=False)
MATE_A = dict(KID, glasses=None, hair="spiky", freckles=True, droop=0.15)
MATE_B = dict(KID, A=144, B=164, glasses=None, hair="pony", lashes=True, droop=0.15, mouth_w=28)
TEACHER = dict(TONY, A=138, B=200, unit=112 / 200, eyes=56, eye_y=-30, eye_k=0.9, glasses=(46, 40), hair="bald", beard=False, moustache=True,
               nose="long", mouth_w=36, droop=0.45, bags=True)
ADULT_W = dict(TONY, A=146, B=180, unit=106 / 180, eyes=58, eye_y=-24, eye_k=0.95, glasses=None, hair="long", beard=False, moustache=False,
               nose="small", mouth_w=34, droop=0.2, bags=False, lashes=True)
ADULT_M = dict(TONY, A=156, B=192, unit=112 / 192, glasses=None, hair="short", beard=False, moustache=False, nose="long", droop=0.3)
ADULT_B = dict(TONY, glasses=None, droop=0.3)


class Head2:
    """A flat head: head units -> the world, through its turn, nod and tilt."""

    def __init__(self, cx, cy, k, tilt=0.0, turn=0.0, nod=0.0):
        self.cx, self.cy, self.k = cx, cy, k
        self.turn, self.nod = max(-1.0, min(1.0, turn)), max(-1.0, min(1.0, nod))
        a = math.radians(tilt)
        self.c, self.s = math.cos(a), math.sin(a)

    def pt(self, x, y, par=1.0):
        """par: how much the point moves when the head turns or nods (the nose more, the jaw's edge less)."""
        x2 = x + self.turn * 32 * par
        y2 = y - self.nod * 18 * par
        return (self.cx + self.k * (x2 * self.c - y2 * self.s), self.cy + self.k * (x2 * self.s + y2 * self.c))

    def pts(self, pts, par=1.0):
        return [self.pt(x, y, par) for x, y in pts]


def mirror(pts, side):
    return [(x * side, y) for x, y in pts]


def ex_of(P):
    e = dict(gx=0.0, gy=0.0, blink=0.0, squint=0.0, smile=0.0, open=0.0, brow=0.0, worry=0.0)
    e.update(P.get("ex", {}))
    return e


def head_of(P):
    f = P["face"]
    k = P["s"] * P["head_k"] * f["unit"]
    c = body_point(P, P["hdx"], P["hdy"] - (f["B"] * f["unit"] * P["head_k"] + 22))
    return Head2(c[0], c[1], k, P["roll"] + P["lean"] * 0.6, P["yaw"] / 24.0, P["pitch"] / 15.0)


def lens_poly(P, side=-1, n=140):
    """One of his lenses (the world), for the camera to go into."""
    hd = head_of(P)
    f = P["face"]
    gx, gy = f["glasses"]
    cx = side * (f["eyes"] + 2)
    return hd.pts([(cx + gx * math.cos(a), f["eye_y"] + 4 + gy * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n)], 1.0)


def draw_head(cv, key, hd, f, e, prog=1.0):
    pen = cv.pen(key + "head")
    rng = cv.rng(key + "hd")
    A, B = f["A"], f["B"]
    turn = hd.turn
    style = f["hair"]

    # --- long hair falls behind the head
    if style == "long":
        back = [(-A - 16, -60), (-A - 34, 60), (-A - 40, 190), (-A - 20, 300), (-60, 318), (60, 318), (A + 20, 300), (A + 40, 190), (A + 34, 60),
                (A + 16, -60), (0, -B - 40)]
        bw = hd.pts(ink.smooth(back, closed=True, n=5), 0.1)
        cv.solid(bw)
        pen.line(bw + bw[:1], w=4.0)
        for k in range(26):
            x0 = -A - 30 + (2 * A + 60) * (k + 0.5) / 26
            pen.line(hd.pts([(x0, 60 + 30 * math.sin(k)), (x0 + 6 * math.sin(k * 1.7), 180), (x0 - 4, 290)], 0.1), w=1.4, amp=1.2)
    if style == "pony":  # a ponytail behind, on our right
        tail = [(A * 0.55, -150), (A + 40, -110), (A + 64, 10), (A + 50, 130), (A + 20, 170), (A + 18, 60), (A * 0.8, -60)]
        tw = hd.pts(ink.smooth(tail, closed=True, n=5), 0.1)
        cv.solid(tw)
        pen.line(tw + tw[:1], w=4.0)
        for k in range(7):
            pen.line(hd.pts([(A * 0.7 + 8 * k, -120 + 6 * k), (A + 30 + 4 * k, 0), (A + 26, 120 - 10 * k)], 0.1), w=1.4, amp=1.0)

    # --- the ears (the one on the side he turns to goes behind)
    for side in (-1, 1):
        if side * turn > 0.45:
            continue
        ear = arc(side * (A + 3) - turn * 8, -2, 16, 34, 100, 280, 20) if side < 0 else arc(A + 3 - turn * 8, -2, 16, 34, -80, 100, 20)
        ew = hd.pts(ear, 0.15)
        cv.solid(ew + [hd.pt(side * (A - 20), -30, 0.15), hd.pt(side * (A - 20), 30, 0.15)])
        pen.line(ew, w=3.5)
        pen.line(hd.pts(arc(side * (A + 2) - turn * 8, 0, 7, 18, 120 if side < 0 else -60, 240 if side < 0 else 60, 10), 0.15), w=1.8)

    # --- the head itself: black (it hides what is behind it), its jaw, its temples
    head_fill = arc(turn * 6, 0, A, B, 0, 360, 72)
    cv.solid(hd.pts(head_fill, 0.15))
    pen.line(hd.pts(arc(turn * 6, 0, A, B, 12, 168, 64), 0.15), w=5)
    pen.line(hd.pts(arc(turn * 6, 0, A, B, 168, 200, 12), 0.15), w=4)
    pen.line(hd.pts(arc(turn * 6, 0, A, B, -20, 12, 12), 0.15), w=4)

    # --- the hair
    if style in ("slick", "long", "pony", "short"):
        low = {"slick": 100, "long": 90, "pony": 92, "short": 84}[style]
        hairline = arc(0, -30, A - 7, low, 192, 338, 40)
        top = arc(0, -40, A + 11, B + 25, 186, 354, 40)
        hl, tp = hd.pts(hairline, 0.55), hd.pts(top, 0.2)
        cv.solid(hl + tp[::-1])
        pen.line(tp, w=4.5)
        n_str = {"slick": 95, "long": 70, "pony": 80, "short": 60}[style]
        for k in range(n_str):
            u = rng.uniform(0.02, 0.98)
            i = int(u * (len(hairline) - 1))
            x0, y0 = hairline[i]
            if style == "short":  # short strokes, upward
                j = min(len(top) - 1, i + rng.integers(0, 3))
                x1, y1 = top[j]
                x1, y1 = x0 + (x1 - x0) * 0.45, y0 + (y1 - y0) * 0.45
                pen.line(hd.pts([(x0, y0 - 2), (x1, y1)], 0.4), w=rng.uniform(1.2, 2.4), amp=0.6)
                continue
            if style in ("long", "pony"):  # parted in the middle, combed to the sides
                x1, y1 = top[min(len(top) - 1, max(0, len(top) // 2 + (rng.integers(-2, 3))))]
            else:  # slicked back
                x1, y1 = top[min(len(top) - 1, i + rng.integers(3, 9))]
            mx, my = (x0 + x1) / 2 + rng.uniform(-10, 10), (y0 + y1) / 2 - rng.uniform(10, 30)
            pen.line(hd.pts(bez((x0, y0 - 2), (x0 + 4, y0 - 30), (mx, my), (x1, y1 + 4), 16), 0.4), w=rng.uniform(1.2, 2.8), amp=0.8)
        if style == "slick":  # a few strands fallen on his temple
            for sx, sy in ((-150, -70), (-138, -76), (-122, -84)):
                pen.line(hd.pts(bez((sx, sy), (sx - 14, sy + 30), (sx - 16, sy + 60), (sx - 4, sy + 92), 14), 0.5), w=1.6)
    elif style == "bowl":  # a child's bowl cut, its fringe over the forehead
        top = arc(0, -30, A + 14, B + 30, 182, 358, 44)
        fringe = [(A + 10, -40), (A - 20, -66), (90, -78), (50, -70), (20, -84), (-20, -72), (-60, -86), (-100, -74), (-A + 14, -60), (-A - 10, -40)]
        fringe = ink.smooth(fringe, n=4)
        tp, fr = hd.pts(top, 0.2), hd.pts(fringe, 0.5)
        cv.solid(tp + fr)
        pen.line(tp, w=4.5)
        pen.line(fr, w=3.0)
        for k in range(64):  # strands from the crown down to the fringe
            u = rng.uniform(0.03, 0.97)
            q = fringe[int(u * (len(fringe) - 1))]
            c0 = (q[0] * 0.25, -B - 10)
            pen.line(hd.pts(bez(c0, (q[0] * 0.5, -B + 30), (q[0] * 0.9, q[1] - 50), (q[0], q[1] - 4), 14), 0.35), w=rng.uniform(1.1, 2.4), amp=0.8)
    elif style == "spiky":  # short spikes
        top = arc(0, -40, A + 6, B + 18, 190, 350, 30)
        tp = hd.pts(top, 0.2)
        spikes = []
        for i, (x, y) in enumerate(top):
            out = 26 if i % 2 else 0
            a = math.atan2(y + 40, x)
            spikes.append((x + out * math.cos(a), y + out * math.sin(a)))
        sp = hd.pts(spikes, 0.2)
        hl = hd.pts(arc(0, -30, A - 8, 90, 194, 346, 30), 0.55)
        cv.solid(hl + sp[::-1])
        pen.line(sp, w=3.6)
        for k in range(40):
            u = rng.uniform(0.05, 0.95)
            q = top[int(u * (len(top) - 1))]
            pen.line(hd.pts([(q[0] * 0.8, q[1] * 0.75 - 6), (q[0], q[1])], 0.35), w=1.6, amp=0.6)
    elif style == "bald":  # a crown with hair only round the sides
        pen.line(hd.pts(arc(0, -30, A + 4, B + 16, 196, 344, 40), 0.2), w=4.5)
        for side in (-1, 1):
            side_h = [(side * (A + 2), -10), (side * (A + 8), -60), (side * (A - 10), -110), (side * (A - 40), -128)]
            pen.line(hd.pts(side_h, 0.3), w=3.0)
            for k in range(14):
                y0 = -18 - 7 * k
                pen.line(hd.pts([(side * (A - 2), y0), (side * (A - 16), y0 - 10)], 0.3), w=1.4, amp=0.5)
        pen.line(hd.pts(bez((-50, -150), (-20, -160), (20, -160), (50, -150), 10), 0.3), w=1.6)  # the light on his forehead

    # --- the beard: short strokes over the chin and the jaw
    if f["beard"]:
        for k in range(170):
            a = math.radians(rng.uniform(25, 155))
            rr = rng.uniform(0.78, 0.99)
            x, y = (A - 5) * rr * math.cos(a), (B - 4) * rr * math.sin(a)
            if y < 95:
                continue
            pen.line(hd.pts([(x, y), (x + rng.uniform(-4, 4), y + rng.uniform(10, 20))], 0.3), w=1.7, amp=0.3)

    # --- the eyes: a lid, a lower lid, a white pupil looking where he looks; bags; the brows
    ex0, ey0 = f["eyes"], f["eye_y"]
    kz = f["eye_k"]
    openness = clip01(1 - f["droop"] - e["blink"] * (1 - f["droop"]))
    squint = e["squint"]
    gx, gy = e["gx"], e["gy"]
    for side in (-1, 1):
        far = 1 - 0.18 * max(0.0, side * turn)  # the eye on the side he turns to narrows a little
        cx, cy = side * ex0, ey0

        def E(pts):
            return hd.pts([(cx + side * (x - cx) * far * kz if False else cx + side * x * far * kz, cy + y * kz) for x, y in pts], 1.0)
        h_lid = 4 + 18 * openness
        if squint > 0.55:  # laughing: shut, curved up
            pen.line(E(bez((-28, 6), (-12, -10), (12, -10), (30, 6), 16)), w=4.2)
        elif openness < 0.08:  # a blink: shut, curved down
            pen.line(E(bez((-30, 2), (-12, 10), (12, 10), (32, 3), 16)), w=4.2)
        else:
            lid = bez((-30, 0), (-12, -h_lid), (14, -h_lid), (32, 2), 18)
            lower_y = 14 - 9 * squint
            lower = bez((-26, 6), (-8, lower_y), (12, lower_y), (28, 6), 16)
            px, py = max(-14, min(14, gx * 13)) * side, 4 + gy * 6
            pr = 9.0
            cv.disc(*E([(px, py)])[0], pr * kz * hd.k)  # the pupil
            # what of the pupil is under the lid is hidden
            cover = lid + [(32, -40), (-30, -40)]
            cv.solid(E(cover))
            pen.line(E(lid), w=4.5)
            pen.line(E(lower), w=2.0)
            if f["lashes"]:
                for k in range(3):
                    x0 = 16 + 7 * k
                    pen.line(E([(x0, -h_lid * 0.6 + 2 * k), (x0 + 6, -h_lid * 0.6 - 8 + 2 * k)]), w=2.0, amp=0.3)
        if f["bags"]:
            pen.line(E(bez((-22, 26), (-6, 33), (10, 33), (24, 26), 12)), w=1.6)
        # the brow: up, knitted (worry: its inner end up), frowning (brow < 0: its inner end down)
        b = e["brow"]
        wor = e["worry"]
        inner_dy = -10 * wor + 8 * max(0.0, -b)
        brow_pts = bez((-34, -34 - 8 * b + inner_dy * 0), (-12, -44 - 8 * b), (12, -44 - 8 * b), (36, -36 - 8 * b), 18)
        # its inner end (toward the nose) moves: for the left eye that is its right end, for the right eye its left one
        brow_pts = [(x, y + inner_dy * clip01((x + 34) / 70)) for x, y in brow_pts]
        pen.line(E(brow_pts), w=6)

    # --- the glasses: round wire, a glint in each, the bridge, the arms
    if f["glasses"]:
        gxr, gyr = f["glasses"]
        for side in (-1, 1):
            far = 1 - 0.15 * max(0.0, side * turn)
            cx = side * (ex0 + 2)
            cy = ey0 + 4
            ring = [(cx + gxr * far * math.cos(a), cy + gyr * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 70)]
            pen.line(hd.pts(ring, 1.0), w=2.6, amp=0.8)
            glint = [(cx + 0.7 * gxr * far * math.cos(a), cy + 0.7 * gyr * math.sin(a)) for a in np.linspace(math.radians(200), math.radians(242), 8)]
            pen.line(hd.pts(glint, 1.0), w=3.2, amp=0.4)
            arm_x = side * (ex0 + 2 + gxr * far)
            if side * turn < 0.5:
                pen.line(hd.pts([(arm_x, cy - 6), (side * (A - 3), cy - 16)], 0.6), w=2.4)
        bx = ex0 + 2 - gxr
        pen.line(hd.pts(bez((-bx, ey0 - 2), (-bx * 0.4, ey0 - 14), (bx * 0.4, ey0 - 14), (bx, ey0 - 2), 10), 1.0), w=2.4)

    # --- the nose
    if f["nose"] == "tony":
        pen.line(hd.pts(bez((2, -20), (-6, 10), (-22, 30), (-8, 40), 20), 1.3), w=3)
        pen.line(hd.pts(bez((-8, 40), (8, 46), (26, 40), (30, 30), 14), 1.3), w=3)
    elif f["nose"] == "long":
        pen.line(hd.pts(bez((4, -24), (-4, 14), (-20, 44), (-6, 54), 20), 1.3), w=3)
        pen.line(hd.pts(bez((-6, 54), (10, 60), (26, 52), (28, 42), 14), 1.3), w=3)
    else:  # small
        pen.line(hd.pts(bez((-4, 8), (-12, 26), (-10, 36), (2, 36), 12), 1.3), w=3)
        pen.line(hd.pts(bez((2, 36), (10, 37), (14, 32), (12, 28), 8), 1.3), w=2.4)

    # --- the mouth: flat, smiling, open
    mw = f["mouth_w"]
    sm, op = e["smile"], e["open"]
    my = 104 if f["beard"] or f["moustache"] else 92 - (0 if f["B"] > 170 else 6)
    if f["nose"] == "long":
        my += 12
    cy_ = my + 3 * sm
    upper = bez((-mw, my - 10 * sm), (-mw * 0.32, cy_ - 6), (mw * 0.32, cy_ - 6), (mw, my - 10 * sm), 16)
    if op > 0.05:
        lower = bez((-mw, my - 10 * sm), (-mw * 0.4, cy_ + 34 * op), (mw * 0.4, cy_ + 34 * op), (mw, my - 10 * sm), 16)
        cv.solid(hd.pts(upper + lower[::-1], 1.0))
        pen.line(hd.pts(upper, 1.0), w=3.4)
        pen.line(hd.pts(lower, 1.0), w=3.0)
        if op > 0.22:
            teeth = bez((-mw * 0.7, my - 6 * sm + 4), (-mw * 0.2, cy_ + 2), (mw * 0.2, cy_ + 2), (mw * 0.7, my - 6 * sm + 4), 10)
            pen.line(hd.pts(teeth, 1.0), w=2.0)
    else:
        pen.line(hd.pts(upper, 1.0), w=3.5)
    lip_y = my + 18 + 30 * op
    pen.line(hd.pts(bez((-mw * 0.7, lip_y - 2 * sm), (-mw * 0.2, lip_y + 6), (mw * 0.2, lip_y + 6), (mw * 0.8, lip_y - 2 * sm), 12), 1.0), w=2.2)
    if f["moustache"]:  # its edge, and its hairs, down from it
        must = bez((-mw - 26, my - 32 - 4 * sm), (-mw * 0.5, my - 52), (mw * 0.5, my - 52), (mw + 26, my - 32 - 4 * sm), 18)
        pen.line(hd.pts(must, 1.0), w=5)
        for k in range(26):
            x, y = must[1 + int((k + 0.5) / 26 * (len(must) - 3))]
            x += rng.uniform(-3, 3)
            pen.line(hd.pts([(x, y + 2), (x + 0.15 * x * 0.2 + rng.uniform(-2, 2), y + rng.uniform(9, 15))], 1.0), w=1.8, amp=0.3)
    if f["freckles"]:
        for side in (-1, 1):
            for k in range(5):
                q = hd.pt(side * (ex0 + rng.uniform(-18, 18)), ey0 + 46 + rng.uniform(-8, 10), 1.0)
                cv.disc(q[0], q[1], 2.2 * hd.k)
    return hd


# --- bodies
def draw_body(cv, key, P, prog=1.0):
    """The torso (a contour, its folds, its shadow side hatched), the collar, the neck, as draw_test drew them."""
    s, bd = P["s"], P["build"]
    pen = cv.pen(key + "body")
    up = P["breath"] * 4 + P["shrug"] * 20
    shy = 8 * P["shrug"]

    def B(x, y):
        return tuple(body_point(P, x, y))
    # the neck: two lines, hatched between
    nk = 40 * bd ** 0.5
    neck = [B(-nk, -78), B(nk, -78), B(nk + 2, 6), B(-nk - 2, 6)]
    cv.solid(neck)
    pen.line([B(-nk, -70), B(-nk - 2, 4)], w=4)
    pen.line([B(nk, -70), B(nk + 2, 4)], w=4)
    pen.hatch(neck, 70 + P["lean"], 14 * s / 1.6, w=1.4)
    # the torso
    L_side = [(-54, -4), (-104, 10 - up * 0.7), (-150 + shy, 34 - up), (-166 + shy, 76 - up * 0.6), (-158, 140), (-146, 240), (-138, 420), (-136, 760)]
    L_side = [(x * (bd if i > 0 else bd ** 0.5), y) for i, (x, y) in enumerate(L_side)]
    R_side = [(-x, y) for x, y in L_side]
    torso = [B(x, y) for x, y in ink.smooth(L_side, n=5)] + [B(x, y) for x, y in ink.smooth(R_side, n=5)[::-1]]
    cv.solid(torso)
    n2 = len(torso) // 2
    pen.line(torso[:n2], w=5)
    pen.line(torso[n2:], w=5)
    # its shadow side, hatched (as in the first drawing)
    shade = [B(-150 * bd, 60), B(-60 * bd, 30), B(-20 * bd, 160), B(-70 * bd, 420), B(-136 * bd, 420)]
    pen.hatch(shade, 62 + P["lean"], 16 * s / 1.6, w=1.5)
    for (x0, y0, x1, y1, x2, y2) in ((-120, 180, -96, 300, -80, 440), (-60, 200, -48, 320, -56, 470), (120, 190, 100, 300, 86, 430),
                                     (70, 220, 62, 330, 72, 460)):
        pen.line([B(x0 * bd, y0), B(x1 * bd + 6, y1), B(x2 * bd, y2)], w=2.4, amp=2.2)
    # the collar: a band, hatched across, its edge
    th = np.linspace(0, math.pi, 30)
    if P["outfit"] == "shirt":
        for side in (-1, 1):
            col = [B(side * 8, 6), B(side * 60, -8), B(side * 72, 44), B(side * 20, 58)]
            cv.solid(col)
            pen.line(col + col[:1], w=3.0)
        tie = [B(-14, 30), B(14, 30), B(22, 300), B(0, 336), B(-22, 300)]
        cv.solid(tie)
        pen.hatch(tie, 40, 9 * s / 1.6, w=1.4)
        pen.line(tie + tie[:1], w=3.0)
    else:
        outer = [B(58 * bd ** 0.5 * math.cos(t), 2 + 24 * math.sin(t)) for t in th]
        inner = [B(44 * bd ** 0.5 * math.cos(t), 0 + 14 * math.sin(t)) for t in th[::-1]]
        cv.solid(outer + inner)
        pen.hatch(outer + inner, 95 + P["lean"], 9 * s / 1.6, w=2.0)
        pen.line(outer, w=3.5)


def finger_outline(base, ang, lengths, widths, curls):
    """A finger's outline: a chain of bones from its base, rounded at the tip."""
    pts = [np.asarray(base, float)]
    a = ang
    for Lseg, cu in zip(lengths, curls):
        a += cu
        pts.append(pts[-1] + Lseg * np.array([math.cos(a), math.sin(a)]))
    left, right = ink.limb([tuple(q) for q in pts], widths, n=4)
    tip = pts[-1]
    r = widths[-1] / 2
    d = np.array([math.cos(a), math.sin(a)])
    nrm = np.array([-d[1], d[0]])
    cap = [tuple(tip + r * (math.cos(t) * nrm + math.sin(t) * d)) for t in np.linspace(0, math.pi, 9)]
    return left + cap[::-1][1:-1] + right[::-1], pts


def shape(cv, pen, poly, w=3.6, closed=True):
    cv.solid(poly)
    pen.line(list(poly) + ([poly[0]] if closed else []), w=w)


def hand_open(cv, key, wrist, ang, L, side, spread=1.0, curl=0.0):
    """A hand seen from its palm, outlined: four fingers and a thumb."""
    pen = cv.pen(key + "hand")
    a = math.radians(ang)
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([math.cos(a + side * math.pi / 2), math.sin(a + side * math.pi / 2)])
    W0 = np.asarray(wrist, float)

    def at(pu, pv):
        return tuple(W0 + u * pu * L + v * pv * L)
    for k, (fv, fl, fw, fa) in enumerate(((0.17, 0.42, 0.11, 0.1), (0.055, 0.46, 0.115, 0.02), (-0.06, 0.43, 0.11, -0.08), (-0.165, 0.34, 0.095, -0.18))):
        poly, _ = finger_outline(at(0.5, fv), a + side * fa * spread, [fl * 0.5 * L, fl * 0.5 * L], [fw * L, fw * L * 0.95, fw * L * 0.85],
                                 [0.0, side * 0.5 * curl])
        shape(cv, pen, poly, w=3.2)
    palm = ink.smooth([at(0.0, -0.17), at(0.1, -0.21), at(0.56, -0.22), at(0.6, 0.0), at(0.56, 0.2), at(0.3, 0.25), at(0.0, 0.17)], closed=True, n=4)
    shape(cv, pen, palm, w=3.6)
    pen.line([at(0.4, -0.18), at(0.36, 0.0), at(0.42, 0.16)], w=1.6)
    pen.hatch([at(0.1, -0.2), at(0.5, -0.21), at(0.45, -0.05), at(0.12, -0.08)], ang + 70, 9, w=1.2)
    poly, _ = finger_outline(at(0.16, 0.2), a + side * (0.95 - 0.5 * curl), [0.2 * L, 0.17 * L], [0.13 * L, 0.12 * L, 0.1 * L], [0, -side * 0.3])
    shape(cv, pen, poly, w=3.2)


def hand_fist(cv, key, wrist, ang, L, side, index=False):
    """A fist (holding something), the index finger out to point when asked."""
    pen = cv.pen(key + "fist")
    a = math.radians(ang)
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([math.cos(a + side * math.pi / 2), math.sin(a + side * math.pi / 2)])
    W0 = np.asarray(wrist, float)

    def at(pu, pv):
        return tuple(W0 + u * pu * L + v * pv * L)
    if index:
        poly, _ = finger_outline(at(0.5, 0.12), a + side * 0.05, [0.26 * L, 0.24 * L], [0.11 * L, 0.1 * L, 0.09 * L], [0, 0])
        shape(cv, pen, poly, w=3.2)
    fist = ink.smooth([at(0.0, -0.17), at(0.3, -0.25), at(0.58, -0.2), at(0.64, 0.0), at(0.56, 0.22), at(0.25, 0.24), at(0.0, 0.17)], closed=True, n=4)
    shape(cv, pen, fist, w=3.6)
    for k in range(2 if index else 3):
        q = 0.16 - 0.12 * k - (0.0 if index else 0.0)
        pen.line([at(0.42, q - 0.08), at(0.62, q - 0.06)], w=1.8)
    pen.line([at(0.2, 0.2), at(0.42, 0.16), at(0.5, 0.06)], w=2.4)  # the thumb over it


def draw_arm(cv, key, P, side, arm):
    """An arm: the sleeve, the bare arm (two lines), the hand."""
    s, bd = P["s"], P["build"]
    up = P["breath"] * 4 + P["shrug"] * 20
    sh = body_point(P, side * 138 * bd, 58 - up)
    l1, l2 = 228 * s * arm.get("k1", 1.0) * bd ** 0.5, 205 * s * arm.get("k2", 1.0) * bd ** 0.5
    el, wr = ik(sh, arm["wrist"], l1, l2, arm.get("elbow", (side * 0.6, 1.0)))
    pen = cv.pen(key + "arm")
    sw = s * bd ** 0.6
    upper = [tuple(sh), tuple((sh + el) / 2 + np.array([side * 4 * sw, 0])), tuple(el)]
    fore = [tuple(el), tuple((el + wr) / 2), tuple(wr)]
    for chain, widths in ((fore, [50 * sw, 46 * sw, 38 * sw]), (upper, [62 * sw, 56 * sw, 50 * sw])):
        left, right = ink.limb(chain, widths, n=6)
        cv.solid(left + right[::-1])
        pen.line(left, w=4.5)
        pen.line(right, w=4.0)
        # its shadow side: a few strokes along it
        mid = [tuple(np.asarray(l_) * 0.62 + np.asarray(r_) * 0.38) for l_, r_ in zip(left, right)]
        pen.hatch(mid + right[::-1], math.degrees(math.atan2(chain[-1][1] - chain[0][1], chain[-1][0] - chain[0][0])) + 75, 11 * sw / 1.6, w=1.3)
    if arm.get("hand") == "pocket":
        pen.line([tuple(body_point(P, side * 136 * bd, 600)), tuple(body_point(P, side * 104 * bd, 612)), tuple(body_point(P, side * 72 * bd, 624))], w=3.5)
    # the sleeve: its outline, its hem, a fold
    sl_end = sh + (el - sh) * 0.5
    left, right = ink.limb([tuple(sh - (el - sh) * 0.06), tuple((sh + sl_end) / 2), tuple(sl_end)], [82 * sw, 80 * sw, 76 * sw], n=5)
    cv.solid(left + right[::-1])
    pen.line(left, w=4.5)
    pen.line(right, w=4.0)
    pen.line([left[-1], tuple((np.asarray(left[-1]) + np.asarray(right[-1])) / 2 + (el - sh) / (np.hypot(*(el - sh)) + 1e-6) * 6 * sw), right[-1]],
             w=3.5)
    pen.line([tuple(np.asarray(left[2]) * 0.7 + np.asarray(right[3]) * 0.3), tuple(np.asarray(left[3]) * 0.45 + np.asarray(right[4]) * 0.55)], w=2.0,
             amp=1.2)
    hand = arm.get("hand")
    L = 150 * sw
    if hand == "open":
        hand_open(cv, key + "h", wr, arm.get("ang", -90), L, arm.get("thumb", -side), arm.get("spread", 1.0), arm.get("curl", 0.0))
    elif hand == "point":
        hand_fist(cv, key + "h", wr, arm.get("ang", 0), L, arm.get("thumb", -side), index=True)
    elif hand == "fist":
        hand_fist(cv, key + "h", wr, arm.get("ang", 90), L, arm.get("thumb", -side))
    return el, wr


def fingertips(cv, key, pts, ang, L):
    """Fingertips round a phone's edge, from behind it."""
    pen = cv.pen(key)
    for k, q in enumerate(pts):
        wk = (0.11, 0.115, 0.105)[k % 3] * L
        poly, _ = finger_outline(np.asarray(q, float) - np.array([math.cos(ang), math.sin(ang)]) * wk * 0.2, ang, [wk * 0.5], [wk, wk * 0.94], [0.0])
        shape(cv, pen, poly, w=3.0)


def draw_tony(cv, key, P, prog=1.0, screen=None, parts=("body", "head", "arms")):
    """Tony, or anyone (the pose says whose face, what build, what clothes), flat, in lines."""
    out = dict(head=head_of(P), lens=[])
    if "body" in parts:
        draw_body(cv, key, P, prog)
    if "head" in parts:
        out["head"] = draw_head(cv, key, head_of(P), P["face"], ex_of(P), prog)
        if P["face"].get("glasses"):
            out["lens"] = [lens_poly(P, -1), lens_poly(P, 1)]
    if "arms" not in parts:
        return out
    for side, name in ((1, "arm_l"), (-1, "arm_r")):
        if P[name] is not None:
            out[name] = draw_arm(cv, key + name, P, side, P[name])
    ph = P.get("phone")
    if ph is not None:
        k = math.cos(math.radians(ph.get("turn", 0)))
        rig.draw_phone(cv, key + "ph", ph["cx"], ph["cy"], ph["w"], ph["h"], ph.get("angle", 0), ph.get("turn", 0), screen, ph.get("glow", 0), prog)
        a = math.radians(ph.get("angle", 0))
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = -math.sin(a), math.cos(a)
        ww = max(6.0, abs(k) * ph["w"])

        def Q(x, y):
            return np.array([ph["cx"] + x * ww / 2 * ux + y * ph["h"] / 2 * vx, ph["cy"] + x * ww / 2 * uy + y * ph["h"] / 2 * vy])
        L = 150 * P["s"]
        if k > 0.15:  # its screen to us: fingertips round our left edge, the thumb on the right
            fingertips(cv, key + "ft", [Q(-1.0, 0.16 + 0.2 * i) for i in range(3)], a, L * 1.25)
            pen = cv.pen(key + "thumb")
            poly, _ = finger_outline(Q(1.0, 0.62) + np.array([ux, uy]) * 16 * P["s"], a + math.pi + 0.75, [0.2 * L, 0.16 * L],
                                     [0.16 * L, 0.15 * L, 0.13 * L], [0, 0.25])
            shape(cv, pen, poly, w=3.2)
        elif k < -0.15:  # its back to us: his fingers across it
            pen = cv.pen(key + "back")
            for i in range(3):
                poly, _ = finger_outline(Q(-1.06, 0.3 + 0.2 * i), a + 0.05 * i, [ww * 0.34, ww * 0.22], [L * 0.13, L * 0.125, L * 0.11], [0.0, 0.25])
                shape(cv, pen, poly, w=3.0)
    return out


def draw_shadow(cv, key, x, y, s, prog=1.0, rim_side=-1, rise=1.0):
    """Someone close, as a looming shadow: black, outlined, hatched on its lit side."""
    y = y + (1 - rise) * 900 * s
    pen = cv.pen(key + "shadow")
    head = arc(x, y - 190 * s, 92 * s, 112 * s, 0, 360, 48)
    body = ink.smooth([(x - 64 * s, y - 70 * s), (x - 190 * s, y - 20 * s), (x - 252 * s, y + 110 * s), (x - 274 * s, y + 900 * s),
                       (x + 274 * s, y + 900 * s), (x + 252 * s, y + 110 * s), (x + 190 * s, y - 20 * s), (x + 64 * s, y - 70 * s)], n=6)
    neck = [(x - 52 * s, y - 120 * s), (x + 52 * s, y - 120 * s), (x + 64 * s, y - 50 * s), (x - 64 * s, y - 50 * s)]
    for sh in (body, neck, head):
        cv.solid(sh)
    edge_b = [(px + rim_side * 0, py) for px, py in body]
    lit = [(px, py) for px, py in body if (px - x) * rim_side > 0] + [(x, y + 900 * s), (x, y - 70 * s)]
    pen.hatch(lit, 62 * -rim_side, 16 * s, w=1.6)
    pen.line(head + head[:1], w=4.0)
    pen.line(edge_b, w=4.0)


# --- chalk: the grain of the first drawing (small gaps in the white, softened)
_grain = {}


def grain(img_l, v):
    """The white ink, its strokes broken a little, as draw_test's: on the 2x layer."""
    if v not in _grain:
        _grain[v] = np.random.default_rng(7 + v).random((H * S, W * S)) < 0.08
    a = np.asarray(img_l, np.float32).copy()
    a[_grain[v]] *= 0.35
    return Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


def picture(cv):
    """The drawing, chalky, at 1080x1920 (RGB)."""
    w = grain(cv.white, cv.v).resize((W, H), Image.LANCZOS)
    rgb = Image.merge("RGB", (w, w, w))
    for name, col in (("orange", (255, 109, 0)), ("red", (226, 40, 40))):
        im = cv.inks[name]
        if im is not None and im.getbbox():
            rgb.paste(col, (0, 0), grain(im, cv.v).resize((W, H), Image.LANCZOS))
    return rgb
