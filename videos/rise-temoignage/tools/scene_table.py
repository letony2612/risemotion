"""One drawing: Tony at his table, seen from the shoulders, in black ink on white paper (tools/cartoon2.py).
Behind him, a window at night and a shelf; in front of him, his mug in his hands and his phone, RISE on it.
Usage: python3 tools/scene_table.py  -> renders/tony_table.png
"""
import math
from pathlib import Path

import numpy as np

import cartoon as ct
import cartoon2 as c2
import episode1_v7 as v7  # the pen's draw-on, RISE drawn by hand
import ink
import rig
from draw_test import arc, bez
from episode1_v7 import cam

ROOT = Path(__file__).resolve().parents[1]
TONY = dict(c2.TONY, hair="cap")
TABLE_Y = 1355.0  # the table's far edge
MUG = (540.0, 1600.0, 150.0, 165.0)  # centre, width, height


def window(cv):
    """A window at night: its frame, a cross of bars, black panes with the moon and a few stars."""
    pen = cv.pen("window")
    x0, y0, x1, y1 = 40.0, 300.0, 420.0, 1000.0
    cv.fill([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 255)
    xm, ym = (x0 + x1) / 2, y0 + (y1 - y0) * 0.42
    bar = 14
    for poly in ([(xm - bar, y0), (xm + bar, y0), (xm + bar, y1), (xm - bar, y1)], [(x0, ym - bar), (x1, ym - bar), (x1, ym + bar), (x0, ym + bar)]):
        cv.solid(poly)
        pen.line(poly + poly[:1], w=3.0)
    pen.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], w=5.0, fill=0)  # the panes' edge
    for d, w in ((-18, 4.5), (0, 3.0)):  # the frame
        pen.line([(x0 + d, y0 + d), (x1 - d, y0 + d), (x1 - d, y1 - d), (x0 + d, y1 - d), (x0 + d, y0 + d)], w=w)
    pen.line([(x0 - 34, y1 - 18), (x1 + 34, y1 - 18), (x1 + 34, y1 + 10), (x0 - 34, y1 + 10), (x0 - 34, y1 - 18)], w=4.0)  # the sill
    # the moon, a crescent; stars
    mx, my, r = 330.0, 400.0, 46.0
    moon = arc(mx, my, r, r, 0, 360, 40)
    cv.solid(moon)
    cv.fill(arc(mx + 22, my - 12, r * 0.92, r * 0.92, 0, 360, 40), 255)
    for (sx, sy, sr) in ((110, 360, 9), (200, 470, 6), (150, 690, 7), (330, 740, 9), (280, 860, 5), (95, 900, 6)):
        pen.line([(sx - sr, sy), (sx + sr, sy)], w=2.6, amp=0.2, fill=0)
        pen.line([(sx, sy - sr), (sx, sy + sr)], w=2.6, amp=0.2, fill=0)


def shelf(cv):
    """A shelf on the wall: books, one lying down, a plant hanging over its edge."""
    pen = cv.pen("shelf")
    rng = cv.rng("shelf")
    x0, x1, y = 735.0, 1100.0, 650.0
    pen.line([(x0, y), (x1, y)], w=5.0)
    pen.line([(x0, y + 16), (x1, y + 16)], w=3.0)
    pen.line([(x0 + 40, y + 16), (x0 + 60, y + 70), (x0 + 90, y + 16)], w=3.0)  # its bracket
    x = 760.0
    for k, (w, h, dark) in enumerate(((34, 150, True), (28, 170, False), (40, 140, True), (24, 160, False), (36, 128, False))):
        book = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
        if dark:
            cv.fill(book, 255)
            pen.line([(x + 6, y - h + 20), (x + w - 6, y - h + 20)], w=2.0, fill=0)
        else:
            cv.solid(book)
            pen.line(book + book[:1], w=3.0)
            pen.hatch(book, 80, 9, w=1.2)
        x += w + 4
    lying = [(x + 10, y), (x + 150, y), (x + 150, y - 30), (x + 10, y - 30)]
    cv.solid(lying)
    pen.line(lying + lying[:1], w=3.0)
    # the plant: a pot, leaves falling over the edge
    px, py = 1030.0, y
    pot = [(px - 40, py), (px + 40, py), (px + 52, py - 70), (px - 52, py - 70)]
    cv.solid(pot)
    pen.line(pot + pot[:1], w=3.4)
    pen.line([(px - 56, py - 70), (px + 56, py - 70)], w=4.0)
    for k in range(9):
        a = math.radians(rng.uniform(190, 350))
        L = rng.uniform(50, 120)
        bx, by = px + rng.uniform(-30, 30), py - 74
        tip = (bx + L * math.cos(a), by + L * math.sin(a) * 0.8 + (60 if k % 3 == 0 else 0))
        pen.line(bez((bx, by), (bx + (tip[0] - bx) * 0.3, by - 40), (tip[0], tip[1] - 30), tip, 14), w=2.4)
        leaf = [(tip[0] + 18 * math.cos(t), tip[1] + 10 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 16)]
        cv.solid(leaf)
        pen.line(leaf, w=2.4)


def table(cv):
    """The table: its top seen from his side, its boards, the grain of the wood."""
    pen = cv.pen("table")
    rng = cv.rng("table")
    top = [(-40.0, TABLE_Y + 8), (1120.0, TABLE_Y - 8), (1120.0, 1960.0), (-40.0, 1960.0)]
    cv.solid(top)
    pen.line([(-40, TABLE_Y + 8), (1120, TABLE_Y - 8)], w=5.0)
    pen.line([(-40, TABLE_Y + 30), (1120, TABLE_Y + 14)], w=2.4)
    for xf in np.linspace(-200, 1280, 9):  # the boards, toward us
        xn = 540 + (xf - 540) * 1.9
        pen.line([(xf, TABLE_Y + 8 - 16 * (xf / 1080)), (xn, 1960)], w=2.4)
    for k in range(70):  # the grain
        u = rng.uniform(0, 1)
        yy = TABLE_Y + 40 + u * u * 560
        xx = rng.uniform(-20, 1100)
        L = 30 + 60 * u
        pen.line([(xx, yy), (xx + L * 0.5, yy + rng.uniform(-3, 3)), (xx + L, yy + rng.uniform(-4, 4))], w=1.3, amp=0.8)


def phone_on_table(cv):
    """His phone, lying on the table, lit: RISE on it, its light round it."""
    cx, cy, w, h, ang = 835.0, 1740.0, 200.0, 360.0, -14.0
    k = 0.5  # lying down: seen at a slant
    pen = cv.pen("tphone")
    for a in np.linspace(0, 2 * math.pi, 54, endpoint=False):  # its light
        r0, r1 = 1.0, 1.0 + pen.rng.uniform(0.25, 0.6)
        ca, sa = math.cos(a), math.sin(a)
        pen.line([(cx + ca * w * 0.62 * r0, cy + sa * h * k * 0.62 * r0), (cx + ca * w * 0.62 * r1, cy + sa * h * k * 0.62 * r1)], w=1.6, amp=0.3)
    a = math.radians(ang)

    def P(x, y):  # phone units: x across (-1..1), y along (-1..1), then laid down
        px, py = x * w / 2, y * h / 2
        rx, ry = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
        return (cx + rx, cy + ry * k)
    body = [P(x, y) for x, y in _rounded(1.0, 1.0, 0.17)]
    scr = [P(x, y) for x, y in _rounded(0.86, 0.93, 0.11)]
    cv.fill(body, 255)
    cv.solid(scr)
    pen.line(body + body[:1], w=3.4)
    # RISE on it, laid down with it
    rise_w = w * 0.62
    x0, y0 = -rise_w / 2, -v7.OUTLINE["aspect"] * rise_w / 2
    for ctr in v7.OUTLINE["letters"]:
        pts = [P((x0 + q[0] * rise_w) / (w / 2), (y0 + q[1] * rise_w - 0.08 * h / 2) / (h / 2)) for q in ctr]
        cv.pen("trise").line(pts + pts[:1], w=2.4, amp=0.5)
    op = cv.pen("tflame", "orange")
    for ctr in v7.OUTLINE["flame"]:
        pts = [P((x0 + q[0] * rise_w) / (w / 2), (y0 + q[1] * rise_w - 0.08 * h / 2) / (h / 2)) for q in ctr]
        cv.fill(pts, 255, "orange")
        op.line(pts + pts[:1], w=2.0, amp=0.4)


def _rounded(sx, sy, r, n=6):
    pts = []
    for (qx, qy, a0) in ((sx - r, -sy + r, -90), (sx - r, sy - r, 0), (-sx + r, sy - r, 90), (-sx + r, -sy + r, 180)):
        for t in np.linspace(math.radians(a0), math.radians(a0 + 90), n):
            pts.append((qx + r * math.cos(t), qy + r * math.sin(t) * 0.55))
    return pts


def mug(cv):
    """His mug, in his two hands, a little steam over it."""
    cx, cy, w, h = MUG
    pen = cv.pen("mug")
    # its shadow on the table
    shadow = arc(cx + 14, cy + h / 2 + 6, w * 0.62, 22, 0, 360, 30)
    pen.hatch(shadow, 10, 7, w=1.3)
    top_y, bot_y = cy - h / 2, cy + h / 2 - 12
    rim = arc(cx, top_y, w / 2, 20, 0, 360, 40)
    body = ([(cx - w / 2, top_y), (cx - w / 2 + 4, bot_y)] + arc(cx, bot_y, w / 2 - 4, 16, 180, 0, 20) + [(cx + w / 2 - 4, bot_y), (cx + w / 2, top_y)]
            + arc(cx, top_y, w / 2, 20, 0, 180, 20))
    cv.fill(body, 255)
    cv.solid(rim)
    pen.line(rim, w=3.4)
    cv.fill(arc(cx, cy - h / 2 + 4, w / 2 - 10, 13, 0, 360, 30), 255)  # the coffee
    pen.line(arc(cx, cy + 10, w / 2 - 6, 14, 20, 160, 14), w=2.0, fill=0)  # a stripe round it
    for k, x in enumerate((cx - 30, cx + 4, cx + 36)):  # the steam
        pts = [(x + 10 * math.sin(t * 2.2 + k), cy - h / 2 - 30 - t * 46) for t in np.linspace(0, 3, 18)]
        pen.line(pts, w=2.4, amp=0.6)


def mug_hands(cv, s):
    """His hands round the mug: their backs, his fingers over its front."""
    cx, cy, w, h = MUG
    pen = cv.pen("mughands")
    for side in (-1, 1):
        x_edge = cx + side * w / 2
        back = ink.smooth([(x_edge - side * 26, cy - 44), (x_edge + side * 30, cy - 52), (x_edge + side * 70, cy - 20), (x_edge + side * 74, cy + 40),
                           (x_edge + side * 40, cy + 62), (x_edge - side * 22, cy + 48)], closed=True, n=5)
        ct.shape(cv, pen, back, w=3.6)
        for k in range(3):  # the fingers, curled round its front toward each other
            fy = cy - 26 + 27 * k
            x0 = x_edge + side * 6
            x1 = cx + side * (16 + 6 * k)
            finger = ink.smooth([(x0, fy - 12), ((x0 + x1) / 2, fy - 13), (x1, fy - 9), (x1 - side * 6, fy + 11), ((x0 + x1) / 2, fy + 12), (x0, fy + 12)],
                                closed=True, n=4)
            ct.shape(cv, pen, finger, w=3.0)
        pen.line([(x_edge + side * 26, cy - 40), (x_edge + side * 6, cy - 18)], w=2.0)  # the thumb's line


def main():
    P = rig.tony_pose(face=TONY, head_k=1.42, x=540.0, y=1075.0, s=1.55)
    P["ex"] = dict(smile=0.4, brow=0.2, gy=0.05)
    P.update(roll=-2.0, shrug=0.25)
    # his elbows on the table, out to the sides; his forearms coming in to the mug
    P["arm_r"] = dict(wrist=(MUG[0] - MUG[2] / 2 - 50, MUG[1] - 10), hand=None, elbow=(-1.0, 0.15), k2=1.2)
    P["arm_l"] = dict(wrist=(MUG[0] + MUG[2] / 2 + 50, MUG[1] - 10), hand=None, elbow=(1.0, 0.15), k2=1.2)
    cv = rig.Canvas(0)
    with cam():
        window(cv)
        shelf(cv)
        c2.draw_tony(cv, "tony", P, parts=("body", "head"))
        table(cv)
        phone_on_table(cv)
        mug(cv)
        c2.draw_tony(cv, "tony", P, parts=("arms",))
        mug_hands(cv, P["s"])
    out = ROOT / "renders" / "tony_table.png"
    out.parent.mkdir(exist_ok=True)
    c2.picture(cv).save(out)
    print(out)


if __name__ == "__main__":
    main()
