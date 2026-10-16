"""Tony as a friendly cartoon in black ink on white paper (cartoon.py's flat caricature, Tony found it scary):
- white paper, black lines with the grain of a pencil; dark things (his hair, his tee, a phone) are solid
  black with white lines in them;
- an open face: open eyes with black pupils and a glint, soft brows, a light stubble, a smile at rest;
- arms drawn in one piece (shoulder, elbow, wrist; or upper arm and forearm when bent), shorter, close to
  the body, coming out of the sleeves; small rounded hands.
Drawn as cartoon.py draws (white strokes on the 2x layer = ink), then turned into ink on paper.
"""
import math

import numpy as np
from PIL import Image

import cartoon as ct
import draw_test as dt
import ink
from cartoon import Head2, finger_outline
from draw_test import arc, bez
from rig import body_point, clip01, ik

W, H, S = 1080, 1920, dt.S
PAPER = (250, 248, 243)
INK = (24, 22, 22)

TONY = dict(ct.TONY, droop=0.1, bags=False, hair_dark=True, beard_n=120)
KID = dict(ct.KID, droop=0.08, hair_dark=True, beard_n=0)


def head_of(P):
    return ct.head_of(P)


def ex_of(P):
    return ct.ex_of(P)


def draw_head(cv, key, hd, f, e):
    pen = cv.pen(key + "head")
    rng = cv.rng(key + "hd")
    A, B = f["A"], f["B"]
    turn = hd.turn

    # --- the ears
    for side in (-1, 1):
        if side * turn > 0.45:
            continue
        ear = arc(side * (A + 3) - turn * 8, -2, 16, 34, 100, 280, 20) if side < 0 else arc(A + 3 - turn * 8, -2, 16, 34, -80, 100, 20)
        ew = hd.pts(ear, 0.15)
        cv.solid(ew + [hd.pt(side * (A - 20), -30, 0.15), hd.pt(side * (A - 20), 30, 0.15)])
        pen.line(ew, w=3.4)
        pen.line(hd.pts(arc(side * (A + 2) - turn * 8, 0, 7, 18, 120 if side < 0 else -60, 240 if side < 0 else 60, 10), 0.15), w=1.8)

    # --- the face: paper, its outline
    cv.solid(hd.pts(arc(turn * 6, 0, A, B, 0, 360, 72), 0.15))
    pen.line(hd.pts(arc(turn * 6, 0, A, B, 12, 168, 64), 0.15), w=4.6)
    pen.line(hd.pts(arc(turn * 6, 0, A, B, 168, 200, 12), 0.15), w=3.8)
    pen.line(hd.pts(arc(turn * 6, 0, A, B, -20, 12, 12), 0.15), w=3.8)

    # --- the hair, or a cap worn backwards (Tony's idea: simpler than his hair)
    if f.get("hair") == "cap":
        draw_cap(cv, pen, rng, hd, A, B)
    else:
        if f.get("hair") == "bowl":
            top = arc(0, -30, A + 14, B + 30, 182, 358, 44)
            fringe = ink.smooth([(A + 10, -40), (A - 20, -66), (90, -78), (50, -70), (20, -84), (-20, -72), (-60, -86), (-100, -74), (-A + 14, -60),
                                 (-A - 10, -40)], n=4)
            hl, tp = hd.pts(fringe, 0.5)[::-1], hd.pts(top, 0.2)
            cv.fill(hl + tp[::-1], 255)
            line_pts, crown = fringe[::-1], (0, -B - 20)
        else:
            line_pts = ink.smooth([(-A + 10, 18), (-A + 4, -40), (-A + 18, -96), (-108, -132), (-56, -146), (0, -150), (56, -148), (108, -136),
                                   (A - 18, -100), (A - 4, -40), (A - 10, 18)], n=5)
            outer = ink.smooth([(A - 4, 20), (A + 10, -34), (A + 16, -94), (A - 6, -168), (98, -218), (0, -236), (-100, -222), (-A + 8, -170),
                                (-A - 14, -96), (-A - 8, -34), (-A + 4, 20)], n=5)
            hl, tp = hd.pts(line_pts, 0.55), hd.pts(outer, 0.2)
            cv.fill(hl + tp, 255)
            crown = (10, -150)
            for k in range(14):  # a few ends, lying back along its edge
                i = int((k + 0.5) / 14 * (len(outer) - 2))
                q, q2 = np.asarray(outer[i]), np.asarray(outer[i + 1])
                tg = (q2 - q) / (np.hypot(*(q2 - q)) + 1e-9)
                nrm = np.array([tg[1], -tg[0]])
                L_ = rng.uniform(10, 18)
                pen.line(hd.pts([tuple(q - tg * 4), tuple(q + tg * L_ + nrm * 6)], 0.2), w=2.2, amp=0.3)
            for side in (-1, 1):  # the sideburns, down to the stubble
                for k in range(7):
                    x = side * (A - 6 - 3 * k)
                    pen.line(hd.pts([(x, 8 + 2 * k), (x + side * 1.5, 34 + 3 * k)], 0.3), w=1.6, amp=0.3)
        # the light on it: long strokes from the hairline up over the top, combed back (more on the lit side, our left)
        top_pts = outer[::-1] if f.get("hair") != "bowl" else top
        n_l, n_t = len(line_pts), len(top_pts)
        for k in range(44):
            u = min(0.97, abs(rng.normal(0.0, 0.42))) if rng.random() < 0.75 else rng.uniform(0.05, 0.97)
            i = int(u * (n_l - 1))
            x0, y0 = line_pts[i]
            j = min(n_t - 1, max(0, int(u * (n_t - 1)) + int(rng.integers(2, 6))))
            x1, y1 = top_pts[j]
            y1 += 10
            mx, my = (x0 + x1) / 2 + rng.uniform(-8, 8), (y0 + y1) / 2 - rng.uniform(4, 16)
            pen.line(hd.pts(bez((x0, y0 - 7), (x0 + 2, y0 - 28), (mx, my), (x1, y1), 16), 0.35), w=rng.uniform(1.0, 2.3), amp=0.7, fill=0)
        if f.get("hair") != "bowl":
            for sx, sy in ((-104, -132), (-90, -138)):  # two strands fallen on his forehead
                pen.line(hd.pts(bez((sx, sy), (sx - 8, sy + 22), (sx - 12, sy + 44), (sx - 4, sy + 66), 14), 0.55), w=2.2)


    # --- a light stubble round the jaw, a moustache
    for k in range(f.get("beard_n", 0)):
        a = math.radians(rng.uniform(28, 152))
        rr = rng.uniform(0.82, 0.985)
        x, y = (A - 5) * rr * math.cos(a), (B - 4) * rr * math.sin(a)
        if y < 104:
            continue
        pen.line(hd.pts([(x, y), (x + rng.uniform(-3, 3), y + rng.uniform(6, 12))], 0.3), w=1.4, amp=0.3)

    # --- the eyes: open, black pupils with a glint; the brows, soft
    ex0, ey0 = f["eyes"], f["eye_y"]
    kz = f["eye_k"]
    openness = clip01(1 - f["droop"] - e["blink"] * (1 - f["droop"]))
    squint = e["squint"]
    gx, gy = e["gx"], e["gy"]
    for side in (-1, 1):
        far = 1 - 0.18 * max(0.0, side * turn)
        cx, cy = side * ex0, ey0

        def E(pts):  # eye units: x > 0 toward the outer corner, on both sides
            return hd.pts([(cx + side * x * far * kz, cy + y * kz) for x, y in pts], 1.0)
        h_lid = 6 + 16 * openness
        if squint > 0.55:
            pen.line(E(bez((-26, 6), (-10, -10), (12, -10), (28, 6), 16)), w=4.0)
        elif openness < 0.08:
            pen.line(E(bez((-28, 2), (-10, 9), (12, 9), (30, 3), 16)), w=4.0)
        else:
            lid = bez((-28, 2), (-10, -h_lid), (14, -h_lid), (30, 3), 18)
            lower = bez((-24, 8), (-8, 15 - 8 * squint), (12, 15 - 8 * squint), (26, 8), 16)
            px, py = max(-12, min(12, gx * 12)) * side, 5 + gy * 6
            (pxw, pyw), = E([(px, py)])
            cv.disc(pxw, pyw, 9.5 * kz * hd.k, 255)  # the pupil, black
            (gxw, gyw), = E([(px - 3.5 * side, py - 3.5)])
            cv.disc(gxw, gyw, 2.6 * kz * hd.k, 0)  # its glint
            cv.solid(E(lid + [(30, -40), (-28, -40)]))  # what is above the lid is skin
            pen.line(E(lid), w=4.2)
            pen.line(E(lower), w=1.6)
        b, wor = e["brow"], e["worry"]
        brow = bez((-30, -40), (-10, -50), (14, -50), (34, -42), 16)
        brow = [(x, y - 7 * b - 9 * wor * clip01((30 - x) / 64) + 6 * max(0.0, -b) * clip01((30 - x) / 64)) for x, y in brow]
        pen.line(E(brow), w=5.0)

    # --- the glasses
    gxr, gyr = f["glasses"]
    for side in (-1, 1):
        far = 1 - 0.15 * max(0.0, side * turn)
        cx, cy = side * (ex0 + 2), ey0 + 4
        ring = [(cx + gxr * far * math.cos(a), cy + gyr * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 70)]
        pen.line(hd.pts(ring, 1.0), w=3.0, amp=0.7)
        glint = [(cx + 0.72 * gxr * far * math.cos(a), cy + 0.72 * gyr * math.sin(a)) for a in np.linspace(math.radians(204), math.radians(236), 6)]
        pen.line(hd.pts(glint, 1.0), w=2.4, amp=0.3)
        if side * turn < 0.5:
            pen.line(hd.pts([(side * (ex0 + 2 + gxr * far), cy - 6), (side * (A - 3), cy - 16)], 0.6), w=2.6)
    bx = ex0 + 2 - gxr
    pen.line(hd.pts(bez((-bx, ey0 - 2), (-bx * 0.4, ey0 - 12), (bx * 0.4, ey0 - 12), (bx, ey0 - 2), 10), 1.0), w=2.6)

    # --- the nose, the mouth (a smile at rest), the moustache
    pen.line(hd.pts(bez((2, -14), (-6, 12), (-20, 30), (-8, 40), 20), 1.3), w=3.2)
    pen.line(hd.pts(bez((-8, 40), (8, 46), (24, 40), (28, 31), 14), 1.3), w=3.2)
    mw = f["mouth_w"]
    sm, op = e["smile"], e["open"]
    my = 108
    cy_ = my + 4 * sm
    upper = bez((-mw, my - 12 * sm), (-mw * 0.3, cy_ + 2 * sm), (mw * 0.3, cy_ + 2 * sm), (mw, my - 12 * sm), 16)
    if op > 0.05:
        lower = bez((-mw, my - 12 * sm), (-mw * 0.4, cy_ + 34 * op), (mw * 0.4, cy_ + 34 * op), (mw, my - 12 * sm), 16)
        cv.fill(hd.pts(upper + lower[::-1], 1.0), 255)
        if op > 0.22:
            pen.line(hd.pts(bez((-mw * 0.7, my - 8 * sm + 4), (-mw * 0.2, cy_ + 3), (mw * 0.2, cy_ + 3), (mw * 0.7, my - 8 * sm + 4), 10), 1.0), w=3.0,
                     fill=0)
    pen.line(hd.pts(upper, 1.0), w=3.6)
    pen.line(hd.pts(bez((-mw * 0.45, my + 18 + 28 * op), (-mw * 0.1, my + 23 + 28 * op), (mw * 0.1, my + 23 + 28 * op), (mw * 0.45, my + 18 + 28 * op), 10),
                    1.0), w=2.0)
    for side in (-1, 1):  # the corners of the smile
        if sm > 0.15:
            q0 = (side * (mw + 2), my - 12 * sm)
            pen.line(hd.pts([q0, (side * (mw + 9), my - 12 * sm - 7 * sm)], 1.0), w=2.2)
    if f.get("beard_n", 0):  # stubble over the lip, no line (a moustache's line looked odd)
        for k in range(30):
            x = rng.uniform(-mw - 12, mw + 12)
            y = my - 18 - rng.uniform(0, 22) + 8 * (abs(x) / (mw + 12)) ** 2
            pen.line(hd.pts([(x, y), (x + rng.uniform(-2, 2), y + rng.uniform(5, 9))], 1.0), w=1.4, amp=0.3)
    return hd


def draw_cap(cv, pen, rng, hd, A, B):
    """A cap worn backwards: black, its seams and its button white; over the forehead, the opening for its
    strap, a little hair in it; its peak behind, sticking out over the top; hair at the temples below it."""
    # its peak, behind the head: only its end shows, out on our right
    peak = ink.smooth([(40, -196), (130, -214), (A + 70, -214), (A + 104, -198), (A + 92, -180), (130, -174), (40, -168)], closed=True, n=5)
    cv.fill(hd.pts(peak, 0.2), 255)
    pen.line(hd.pts(ink.smooth([(A - 10, -204), (A + 64, -205), (A + 92, -194)], n=6), 0.2), w=1.6, amp=0.3, fill=0)
    pen.line(hd.pts(ink.smooth([(A - 10, -186), (A + 60, -186), (A + 84, -183)], n=6), 0.2), w=1.4, amp=0.3, fill=0)
    band = bez((-A - 6, -56), (-70, -88), (70, -88), (A + 6, -56), 24)
    dome = ink.smooth([(A + 6, -56), (A + 12, -112), (150, -180), (86, -228), (0, -242), (-86, -228), (-150, -180), (-A - 12, -112),
                       (-A - 6, -56)], n=6)
    cv.fill(hd.pts(band + dome, 0.25), 255)
    for xs in (-118, -50, 50, 118):  # its seams, up to the button
        seam = bez((xs, -84 + abs(xs) * 0.2), (xs * 1.04, -150), (xs * 0.6, -208), (0, -238), 14)
        pen.line(hd.pts(seam, 0.25), w=1.7, amp=0.4, fill=0)
    pen.line(hd.pts([(x, y - 9) for x, y in band[2:-2]], 0.25), w=1.4, amp=0.3, fill=0)  # the stitching over its edge
    bx, by = hd.pt(0, -240, 0.25)
    cv.disc(bx, by, 8.5 * hd.k, 0)
    cv.disc(bx, by, 4.5 * hd.k, 255)
    # the opening over the forehead (worn backwards), its strap across, his hair in it
    opening = arc(0, -82, 40, 50, 180, 360, 20)
    cv.solid(hd.pts(opening + [(40, -82), (-40, -82)], 0.3))
    pen.line(hd.pts(opening, 0.3), w=2.4, amp=0.3)
    for k in range(9):
        x = -30 + 7.5 * k
        pen.line(hd.pts([(x, -86), (x + 4, -118 + 10 * abs(x) / 30)], 0.3), w=1.6, amp=0.4)
    strap = [(-48, -98), (48, -98), (48, -82), (-48, -82)]
    cv.fill(hd.pts(strap, 0.3), 255)
    for k in range(5):
        cv.disc(*hd.pt(-28 + 14 * k, -90, 0.3), 2.6 * hd.k, 0)
    # his hair at the temples, below the cap
    for side in (-1, 1):
        for k in range(9):
            x = side * (A - 4 - 3.2 * k)
            pen.line(hd.pts([(x, -58 + 2 * k), (x + side * 2, -18 + 3 * k)], 0.3), w=1.8, amp=0.3)


def draw_body(cv, key, P):
    """A black tee: its mass, white folds, the collar; the neck."""
    s, bd = P["s"], P["build"]
    pen = cv.pen(key + "body")
    up = P["breath"] * 4 + P["shrug"] * 20
    shy = 8 * P["shrug"]

    def B(x, y):
        return tuple(body_point(P, x, y))
    nk = 40 * bd ** 0.5
    neck = [B(-nk, -80), B(nk, -80), B(nk + 3, 8), B(-nk - 3, 8)]
    cv.solid(neck)
    pen.line([B(-nk, -70), B(-nk - 3, 6)], w=3.8)
    pen.line([B(nk, -70), B(nk + 3, 6)], w=3.8)
    pen.hatch([B(-nk, -40), B(nk, -40), B(nk + 2, 0), B(-nk - 2, 0)], 70 + P["lean"], 11 * s / 1.6, w=1.2)  # the shadow under his chin
    L_side = [(-54, -4), (-104, 10 - up * 0.7), (-150 + shy, 34 - up), (-162 + shy, 76 - up * 0.6), (-152, 140), (-142, 240), (-136, 420), (-134, 760)]
    L_side = [(x * (bd if i > 0 else bd ** 0.5), y) for i, (x, y) in enumerate(L_side)]
    R_side = [(-x, y) for x, y in L_side]
    torso = [B(x, y) for x, y in ink.smooth(L_side, n=5)] + [B(x, y) for x, y in ink.smooth(R_side, n=5)[::-1]]
    cv.fill(torso, 255)
    for (x0, y0, x1, y1, x2, y2) in ((-118, 190, -96, 300, -80, 440), (-56, 230, -46, 330, -54, 470), (118, 200, 98, 300, 86, 430),
                                     (66, 240, 60, 340, 70, 470)):
        pen.line([B(x0 * bd, y0), B(x1 * bd + 6, y1), B(x2 * bd, y2)], w=2.2, amp=1.6, fill=0)
    th = np.linspace(0, math.pi, 30)
    outer = [B(58 * bd ** 0.5 * math.cos(t), 2 + 24 * math.sin(t)) for t in th]
    inner = [B(44 * bd ** 0.5 * math.cos(t), 0 + 14 * math.sin(t)) for t in th[::-1]]
    for k in range(9):  # the collar's ribs, white in the black
        t = (k + 0.5) / 9 * math.pi
        pen.line([B(46 * bd ** 0.5 * math.cos(t), 1 + 15 * math.sin(t)), B(56 * bd ** 0.5 * math.cos(t), 2 + 22 * math.sin(t))], w=1.6, amp=0.3, fill=0)
    pen.line(outer, w=2.4, amp=0.4, fill=0)


def arm_outline(sh, el, wr, sw):
    """The arm's shape: one piece when nearly straight; when bent, the upper arm, and the forearm over it."""
    d1, d2 = el - sh, wr - el
    bend = math.degrees(math.acos(max(-1.0, min(1.0, float(d1 @ d2) / (np.hypot(*d1) * np.hypot(*d2) + 1e-9)))))
    out = 1 if (d1[0] * d2[1] - d1[1] * d2[0]) > 0 else -1
    n1 = np.array([-d1[1], d1[0]]) / (np.hypot(*d1) + 1e-9)
    bulge = -out * n1 * 5 * sw  # the biceps, on the outside of the bend
    if bend < 60:
        chain = [tuple(sh), tuple((sh + el) / 2 + bulge), tuple(el), tuple((el + wr) / 2), tuple(wr)]
        left, right = ink.limb(chain, [82 * sw, 74 * sw, 63 * sw, 57 * sw, 47 * sw], n=8)
        return [left + right[::-1]]

    def capsule(chain, widths, cap_start):
        left, right = ink.limb(chain, widths, n=8)
        if not cap_start:
            return left + right[::-1]
        p0 = np.asarray(chain[0], float)
        dd = np.asarray(chain[1], float) - p0
        dd /= np.hypot(*dd) + 1e-9
        nn = np.array([-dd[1], dd[0]])
        r = widths[0] / 2
        cap = [tuple(p0 + r * (math.cos(t) * nn - math.sin(t) * dd)) for t in np.linspace(0, math.pi, 10)]
        return left + right[::-1] + cap[::-1]
    upper = capsule([tuple(el + (el - sh) * 0.1), tuple((sh + el) / 2 + bulge), tuple(sh)], [66 * sw, 74 * sw, 82 * sw], True)
    fore = capsule([tuple(el), tuple((el + wr) / 2), tuple(wr)], [63 * sw, 57 * sw, 47 * sw], True)
    return [upper, fore]


def draw_arm(cv, key, P, side, arm):
    s, bd = P["s"], P["build"]
    up = P["breath"] * 4 + P["shrug"] * 20
    sh = body_point(P, side * 128 * bd, 66 - up)
    l1, l2 = 152 * s * arm.get("k1", 1.0) * bd ** 0.5, 138 * s * arm.get("k2", 1.0) * bd ** 0.5
    el, wr = ik(sh, arm["wrist"], l1, l2, arm.get("elbow", (side * 0.35, 1.0)))
    pen = cv.pen(key + "arm")
    sw = s * bd ** 0.6
    for poly in arm_outline(sh, el, wr, sw):
        cv.solid(poly)
        pen.line(poly + poly[:1], w=4.0)
    # the sleeve over the top of it: black, its hem white
    d = el - sh
    dn = d / (np.hypot(*d) + 1e-9)
    left, right = ink.limb([tuple(sh - d * 0.12), tuple(sh + d * 0.18), tuple(sh + d * 0.42)], [100 * sw, 98 * sw, 94 * sw], n=5)
    cv.fill(left + right[::-1], 255)
    pen.line([tuple(np.asarray(left[-1]) - dn * 5 * sw), tuple(np.asarray(right[-1]) - dn * 5 * sw)], w=2.2, amp=0.4, fill=0)
    pen.line([tuple(np.asarray(left[3]) * 0.6 + np.asarray(right[3]) * 0.4), tuple(np.asarray(left[5]) * 0.4 + np.asarray(right[5]) * 0.6)], w=1.8,
             amp=1.0, fill=0)
    hand = arm.get("hand")
    L = 128 * sw
    if hand == "open":
        hand_open(cv, key + "h", wr, arm.get("ang", -90), L, arm.get("thumb", -side), arm.get("spread", 0.45), arm.get("curl", 0.1))
    elif hand == "fist":
        ct.hand_fist(cv, key + "h", wr, arm.get("ang", 90), L, arm.get("thumb", -side))
    elif hand == "point":
        ct.hand_fist(cv, key + "h", wr, arm.get("ang", 0), L, arm.get("thumb", -side), index=True)
    return el, wr


def hand_open(cv, key, wrist, ang, L, side, spread=0.45, curl=0.1):
    """A small, rounded hand, its fingers close together."""
    pen = cv.pen(key + "hand")
    a = math.radians(ang)
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([math.cos(a + side * math.pi / 2), math.sin(a + side * math.pi / 2)])
    W0 = np.asarray(wrist, float)

    def at(pu, pv):
        return tuple(W0 + u * pu * L + v * pv * L)
    for k, (fv, fl, fw, fa) in enumerate(((0.165, 0.36, 0.125, 0.08), (0.055, 0.4, 0.13, 0.02), (-0.058, 0.37, 0.125, -0.05), (-0.16, 0.29, 0.11, -0.12))):
        poly, _ = finger_outline(at(0.48, fv), a + side * fa * spread, [fl * 0.52 * L, fl * 0.48 * L], [fw * L, fw * L * 0.97, fw * L * 0.9],
                                 [0.0, side * 0.45 * curl])
        ct.shape(cv, pen, poly, w=3.4)
    palm = ink.smooth([at(0.0, -0.17), at(0.12, -0.22), at(0.54, -0.23), at(0.6, 0.0), at(0.54, 0.22), at(0.3, 0.26), at(0.0, 0.18)], closed=True, n=4)
    ct.shape(cv, pen, palm, w=3.8)
    pen.line([at(0.42, -0.14), at(0.38, 0.02), at(0.42, 0.14)], w=1.5)
    poly, _ = finger_outline(at(0.18, 0.21), a + side * (0.85 - 0.4 * curl), [0.17 * L, 0.15 * L], [0.15 * L, 0.14 * L, 0.12 * L], [0, -side * 0.35])
    ct.shape(cv, pen, poly, w=3.4)


def draw_phone(cv, key, ph, screen=None):
    """A phone, held up to show its screen: a black edge, a white screen."""
    cx, cy, w, h, ang = ph["cx"], ph["cy"], ph["w"], ph["h"], ph.get("angle", 0.0)
    body = ct.rig.rounded_rect(cx, cy, w, h, w * 0.17, ang)
    scr = ct.rig.rounded_rect(cx, cy, w * 0.86, h * 0.93, w * 0.11, ang)
    cv.fill(body, 255)
    cv.solid(scr)
    pen = cv.pen(key + "ph")
    pen.line(body + body[:1], w=3.6, amp=0.5)
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)

    def P(x, y):
        return (cx + x * w / 2 * ca - y * h / 2 * sa, cy + x * w / 2 * sa + y * h / 2 * ca)
    pen.line([P(-0.16, -0.955), P(0.16, -0.955)], w=3.0, amp=0.2, fill=0)
    if screen is not None:
        screen(cv, dict(P=P, k=1.0, w=w, h=h, angle=ang, poly=scr))
    return body


def draw_tony(cv, key, P, screen=None, parts=("body", "head", "arms")):
    out = dict(head=head_of(P))
    if "body" in parts:
        draw_body(cv, key, P)
    if "head" in parts:
        out["head"] = draw_head(cv, key, head_of(P), P["face"], ex_of(P))
    if "arms" not in parts:
        return out
    for side, name in ((1, "arm_l"), (-1, "arm_r")):
        if P[name] is not None:
            out[name] = draw_arm(cv, key + name, P, side, P[name])
    ph = P.get("phone")
    if ph is not None:
        draw_phone(cv, key, ph, screen)
        a = math.radians(ph.get("angle", 0))
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = -math.sin(a), math.cos(a)

        def Q(x, y):
            return np.array([ph["cx"] + x * ph["w"] / 2 * ux + y * ph["h"] / 2 * vx, ph["cy"] + x * ph["w"] / 2 * uy + y * ph["h"] / 2 * vy])
        L = 128 * P["s"]
        pen = cv.pen(key + "grip")
        for i in range(4):  # his fingers round its edge, from behind
            q = Q(-1.0, 0.12 + 0.17 * i)
            r = 0.085 * L
            bump_ = [tuple(q + np.array([ux, uy]) * (r * 0.55 * math.cos(t) - r * 0.15) + np.array([vx, vy]) * r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 18)]
            ct.shape(cv, pen, bump_, w=3.2)
        tb = Q(1.0, 0.56) + np.array([ux, uy]) * 0.06 * L
        poly, _ = finger_outline(tb, a + math.pi + 0.45, [0.17 * L, 0.13 * L], [0.2 * L, 0.19 * L, 0.17 * L], [0, 0.3])
        ct.shape(cv, pen, poly, w=3.6)
        pen.line([tuple(Q(1.0, 0.56) - np.array([ux, uy]) * 0.12 * L - np.array([vx, vy]) * 0.04 * L),
                  tuple(Q(1.0, 0.56) - np.array([ux, uy]) * 0.08 * L + np.array([vx, vy]) * 0.05 * L)], w=1.5)  # its nail
    return out


def grain(img_l, v):
    return ct.grain(img_l, v)


def picture(cv):
    """Ink on paper (RGB): the strokes black, the rest paper; the coloured inks on top."""
    k = np.asarray(grain(cv.white, cv.v).resize((W, H), Image.LANCZOS), np.float32)[..., None] / 255.0
    paper = np.array(PAPER, np.float32)
    inkc = np.array(INK, np.float32)
    rgb = Image.fromarray((paper * (1 - k) + inkc * k).astype(np.uint8))
    for name, col in (("orange", (255, 109, 0)), ("red", (214, 30, 30))):
        im = cv.inks[name]
        if im is not None and im.getbbox():
            rgb.paste(col, (0, 0), grain(im, cv.v).resize((W, H), Image.LANCZOS))
    return rgb
