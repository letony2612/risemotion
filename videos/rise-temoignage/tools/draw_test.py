"""Test: a scratchboard drawing (white ink lines on black) of the user, alone at night, head in his hand,
his phone lit on the table, thought bubbles over him. Animated the hand-drawn way: the lines "boil"
(3 slightly different drawings, 8 a second), the bubbles drift, the phone's light breathes.
Usage: python3 draw.py [still]  -> still.png, or frames/ + test_dessin.mp4
"""
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter1d

OUT = Path(__file__).resolve().parent
S = 2  # drawn at twice the size, then reduced: smooth lines
W, H = 1080, 1920
FPS, SECONDS = 24, 5


# the camera: every point goes through it, so a camera move redraws the scene (lines keep their ink)
CAM = [1.0, 540.0, 960.0, 540.0, 960.0]  # zoom, the drawing's point at the middle of the move, where it lands on screen


def T(x, y):
    z, px, py, qx, qy = CAM
    return qx + (x - px) * z, qy + (y - py) * z


def P(pts):
    a = np.array(pts, float).reshape(-1, 2)
    z, px, py, qx, qy = CAM
    return np.stack([qx + (a[:, 0] - px) * z, qy + (a[:, 1] - py) * z], 1) * S


def ink():
    """Lines get a little heavier when the camera is close."""
    return CAM[0] ** 0.35


def dense(pts, step=5):
    pts = P(pts)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(2, int(np.hypot(*(b - a)) / (step * S)))
        out += [a + (b - a) * t for t in np.linspace(0, 1, n, endpoint=False)]
    out.append(pts[-1])
    return np.array(out)


def wobble(arr, rng, amp):
    n = rng.normal(0, 1, arr.shape)
    n = gaussian_filter1d(n, 4, axis=0, mode="nearest") * amp * S * 2.2
    return arr + n


def bez(p0, p1, p2, p3, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3).tolist()


def arc(cx, cy, rx, ry, a0, a1, n=60, rot=0):
    out = []
    for a in np.linspace(math.radians(a0), math.radians(a1), n):
        x, y = rx * math.cos(a), ry * math.sin(a)
        r = math.radians(rot)
        out.append((cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)))
    return out


class Pen:
    def __init__(self, img, rng):
        self.d, self.rng, self.img = ImageDraw.Draw(img), rng, img

    def line(self, pts, w=4, amp=1.6, fill=255):
        p = wobble(dense(pts), self.rng, amp)
        # the ink thins and thickens along the stroke
        ws = w * (0.75 + 0.5 * gaussian_filter1d(self.rng.random(len(p)), 3))
        # only what is on the page is drawn (a stroke can run far off it when the camera is close)
        m = 60 * S
        inside = (p[:, 0] > -m) & (p[:, 0] < W * S + m) & (p[:, 1] > -m) & (p[:, 1] < H * S + m)
        for i in range(len(p) - 1):
            if inside[i] or inside[i + 1]:
                self.d.line([tuple(p[i]), tuple(p[i + 1])], fill=fill, width=max(1, int(ws[i] * S * ink())))
        for j in range(0, len(p), 3):  # round joints
            if inside[j]:
                q, wi = p[j], ws[j]
                r = wi * S * ink() / 2
                self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=fill)

    def disc(self, x0, y0, x1, y1, fill=255):
        """An ellipse in the drawing's coordinates, through the camera."""
        a, b = T(x0, y0), T(x1, y1)
        self.d.ellipse([a[0] * S, a[1] * S, b[0] * S, b[1] * S], fill=fill)

    def poly(self, pts, fill=255):  # fill=0 hides what is behind
        self.d.polygon([tuple(q) for q in wobble(dense(pts + pts[:1]), self.rng, 1.0)], fill=fill)

    def hatch(self, mask_pts, angle, gap, w=2.2, jitter=0.35, length=None):
        """Parallel strokes inside a shape: the scratchboard's way of making grey."""
        m = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(m).polygon([tuple(q) for q in P(mask_pts)], fill=255)
        layer = Image.new("L", self.img.size, 0)
        sub = Pen(layer, self.rng)
        a = math.radians(angle)
        dx, dy = math.cos(a), math.sin(a)
        xs = [p[0] for p in mask_pts]
        ys = [p[1] for p in mask_pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        R = max(max(xs) - min(xs), max(ys) - min(ys))
        for k in np.arange(-R, R, gap):
            ox, oy = cx - dy * k, cy + dx * k
            L = R if length is None else length * (0.7 + 0.6 * self.rng.random())
            s = self.rng.uniform(-0.3, 0.3) * R if length else -R
            sub.line([(ox + dx * s, oy + dy * s), (ox + dx * (s + 2 * L if length is None else s + L), oy + dy * (s + 2 * L if length is None else s + L))],
                     w=w * (1 + self.rng.uniform(-jitter, jitter)), amp=1.0)
        self.img.paste(255, (0, 0), Image.composite(layer, Image.new("L", self.img.size, 0), m))


def bubble(pen, cx, cy, r, symbol):
    """A thought bubble: a rough ring, radial strokes like the reference's, a sign inside."""
    pen.line(arc(cx, cy, r, r, 0, 360, 80), w=3.5)
    for a in np.linspace(0, 360, int(r * 0.9), endpoint=False):
        a += pen.rng.uniform(-2, 2)
        r0 = r * pen.rng.uniform(0.55, 0.7)
        ra = math.radians(a)
        pen.line([(cx + r0 * math.cos(ra), cy + r0 * math.sin(ra)), (cx + r * 0.94 * math.cos(ra), cy + r * 0.94 * math.sin(ra))], w=1.6, amp=0.4)
    s = r * 0.32
    if symbol == "?":
        pen.line(arc(cx, cy - s * 0.6, s * 0.7, s * 0.7, 200, 400, 30) + [(cx, cy + s * 0.5)], w=5)
        pen.disc(cx - 5, cy + s * 0.95 - 5, cx + 5, cy + s * 0.95 + 5)
    elif symbol == "chat":
        pen.line([(cx - s, cy - s * 0.7), (cx + s, cy - s * 0.7), (cx + s, cy + s * 0.4), (cx - s * 0.2, cy + s * 0.4),
                  (cx - s * 0.7, cy + s), (cx - s * 0.5, cy + s * 0.4), (cx - s, cy + s * 0.4), (cx - s, cy - s * 0.7)], w=4)
    elif symbol == "cross":
        pen.line([(cx, cy - s * 1.1), (cx, cy + s * 1.1)], w=5)
        pen.line([(cx - s * 0.65, cy - s * 0.4), (cx + s * 0.65, cy - s * 0.4)], w=5)


def draw(variant, t):
    rng = np.random.default_rng(100 + variant)
    img = Image.new("L", (W * S, H * S), 0)
    pen = Pen(img, rng)

    # --- the table: its edge, the grain of the wood
    pen.line([(-10, 1470), (1090, 1462)], w=5)
    for x in range(40, 1100, 170):
        pen.line([(x, 1475), ((x - 540) * 1.6 + 540, 1920)], w=1.8, amp=1.2)
    pen.hatch([(0, 1478), (1080, 1470), (1080, 1920), (0, 1920)], 8, 26, w=1.3, length=70)

    # --- the body: a dark round-neck tee, only its folds caught in white
    body = [(250, 1470), (300, 1330), (420, 1255), (520, 1232), (720, 1236), (840, 1290), (930, 1400), (960, 1470)]
    pen.line(body, w=5)
    for x0, x1 in ((380, 360), (470, 455), (800, 830), (880, 905)):
        pen.line([(x0, 1300), ((x0 + x1) / 2 + 6, 1390), (x1, 1465)], w=2.4, amp=2.2)
    pen.hatch([(300, 1340), (420, 1262), (470, 1300), (430, 1470), (260, 1470)], 62, 16, w=1.5)
    # the collar: a thick band, hatched across
    collar_o = arc(625, 1215, 125, 48, 10, 170, 40)
    collar_i = arc(625, 1200, 100, 34, 170, 10, 40)
    pen.hatch(collar_o + collar_i, 95, 9, w=2.0)
    pen.line(collar_o, w=3.5)

    # --- the neck
    pen.line([(555, 1120), (562, 1205)], w=4)
    pen.line([(690, 1125), (685, 1205)], w=4)
    pen.hatch([(560, 1150), (690, 1150), (686, 1200), (564, 1200)], 70, 14, w=1.4)

    # --- the head, tilted onto his right hand (on our right)
    hx, hy, tilt = 620, 960, 9
    face = arc(hx, hy, 165, 190, 15, 175, 70, tilt)  # round jaw, cheeks
    pen.line(face, w=5)
    pen.line(arc(hx, hy, 165, 190, 175, 205, 12, tilt), w=4)  # his left temple
    # the beard: short strokes over the chin and the jaw, the moustache
    for k in range(170):
        a = math.radians(rng.uniform(25, 155) + tilt)
        rr = rng.uniform(0.78, 0.99)
        x, y = hx + 160 * rr * math.cos(a), hy + 186 * rr * math.sin(a)
        if y < hy + 95:
            continue
        pen.line([(x, y), (x + rng.uniform(-4, 4), y + rng.uniform(10, 20))], w=1.7, amp=0.3)
    pen.line(bez((hx - 70, hy + 70), (hx - 30, hy + 52), (hx + 30, hy + 55), (hx + 72, hy + 78)), w=5)  # moustache
    pen.line(bez((hx - 40, hy + 108), (hx - 10, hy + 100), (hx + 20, hy + 102), (hx + 48, hy + 112)), w=3.5)  # mouth, flat
    pen.line(bez((hx - 30, hy + 125), (hx, hy + 132), (hx + 25, hy + 130), (hx + 40, hy + 124)), w=2.2)  # lower lip
    # the nose
    pen.line(bez((hx + 2, hy - 20), (hx - 6, hy + 10), (hx - 22, hy + 30), (hx - 8, hy + 40)), w=3)
    pen.line(bez((hx - 8, hy + 40), (hx + 8, hy + 46), (hx + 26, hy + 40), (hx + 30, hy + 30)), w=3)
    # the eyes: tired, half shut, looking down at the phone
    for ex, ey in ((hx - 72, hy - 30), (hx + 60, hy - 22)):
        pen.line(bez((ex - 30, ey), (ex - 12, ey - 12), (ex + 14, ey - 12), (ex + 32, ey + 2)), w=4.5)  # heavy lid
        pen.line(bez((ex - 26, ey + 6), (ex - 8, ey + 14), (ex + 12, ey + 14), (ex + 28, ey + 6)), w=2)
        pen.disc(ex - 9, ey - 2, ex + 9, ey + 12)  # the look, down
        pen.line(bez((ex - 22, ey + 26), (ex - 6, ey + 33), (ex + 10, ey + 33), (ex + 24, ey + 26)), w=1.6)  # the bags
        pen.line(bez((ex - 34, ey - 34), (ex - 12, ey - 44), (ex + 12, ey - 44), (ex + 36, ey - 36)), w=6)  # brow
    # the glasses: thin round wire frames, his own
    for gx, gy in ((hx - 70, hy - 24), (hx + 62, hy - 16)):
        pen.line(arc(gx, gy, 58, 52, 0, 360, 70), w=2.6, amp=0.8)
    pen.line(bez((hx - 14, hy - 34), (hx - 6, hy - 44), (hx + 2, hy - 44), (hx + 6, hy - 30)), w=2.4)  # the bridge
    pen.line([(hx - 128, hy - 30), (hx - 162, hy - 40)], w=2.4)  # the temple arm
    pen.line(arc(hx - 168, hy - 2, 16, 34, 100, 280, 20), w=3.5)  # his left ear
    # the hair: slicked back, black with white highlights, a few strands falling on his left temple
    hairline = arc(hx, hy - 30, 158, 100, 192, 338, 40, tilt)
    top = arc(hx + 6, hy - 40, 176, 215, 188, 342, 40, tilt)
    pen.poly(hairline + top[::-1], fill=0)
    pen.line(top, w=4.5)
    for k in range(95):
        u = rng.uniform(0.02, 0.98)
        i = int(u * (len(hairline) - 1))
        x0, y0 = hairline[i]
        x1, y1 = top[min(len(top) - 1, i + rng.integers(3, 9))]
        mx, my = (x0 + x1) / 2 + rng.uniform(-10, 10), (y0 + y1) / 2 - rng.uniform(10, 30)
        pen.line(bez((x0, y0 - 2), (x0 + 4, y0 - 30), (mx, my), (x1, y1 + 4)), w=rng.uniform(1.2, 2.8), amp=0.8)
    for sx, sy in ((hx - 150, hy - 70), (hx - 138, hy - 76), (hx - 122, hy - 84)):  # loose strands
        pen.line(bez((sx, sy), (sx - 14, sy + 30), (sx - 16, sy + 60), (sx - 4, sy + 92)), w=1.6)

    # --- the hand holding his cheek, the forearm down to the table
    hand = [(762, 1160), (748, 1080), (738, 1000), (742, 930), (760, 885), (788, 868), (815, 872), (838, 890),
            (852, 930), (858, 1000), (855, 1080), (850, 1160)]
    arm = [(762, 1160), (790, 1300), (812, 1465), (912, 1465), (888, 1300), (850, 1160)]
    pen.poly(arm, fill=0)
    pen.poly(hand, fill=0)
    pen.line(hand, w=5)
    pen.line([(762, 1160), (790, 1300), (812, 1465)], w=5)
    pen.line([(850, 1160), (888, 1300), (912, 1465)], w=5)
    for fx in (768, 795, 822):  # between the fingers
        pen.line(bez((fx + 4, 1010), (fx, 960), (fx + 2, 920), (fx + 8, 885)), w=2.6)
    pen.line(bez((748, 1080), (735, 1060), (728, 1030), (740, 1005)), w=3.5)  # the thumb, under the cheekbone
    pen.hatch([(800, 1010), (850, 1000), (852, 1150), (805, 1150)], 80, 12, w=1.3)  # its shadow side
    pen.hatch([(860, 1200), (890, 1300), (908, 1460), (870, 1460), (845, 1300)], 75, 11, w=1.3)
    pen.line(bez((775, 1215), (800, 1230), (830, 1228), (855, 1215)), w=2.2)  # the wrist

    # --- the phone on the table, lit: its light breathes
    glow = 0.75 + 0.25 * math.sin(t * 2 * math.pi / 2.5)
    ph = [(170, 1530), (390, 1500), (420, 1610), (195, 1645)]
    pen.line(ph + ph[:1], w=4)
    scr = [(188, 1538), (380, 1512), (405, 1600), (210, 1630)]
    pen.poly(scr)
    fx, fy = 296, 1572  # the flame of RISE, black on the light
    pen.d.polygon([(T(*q)[0] * S, T(*q)[1] * S) for q in bez((fx, fy - 26), (fx + 22, fy - 4), (fx + 16, fy + 18), (fx, fy + 18), 20)
                   + bez((fx, fy + 18), (fx - 16, fy + 18), (fx - 20, fy - 2), (fx, fy - 26), 20)], fill=0)
    for a in np.linspace(-170, 10, 46):  # the light, scratched out around it
        ra = math.radians(a + rng.uniform(-2, 2))
        r0, r1 = 140, 140 + 230 * glow * rng.uniform(0.5, 1.0)
        pen.line([(295 + r0 * math.cos(ra), 1575 + r0 * 0.55 * math.sin(ra)), (295 + r1 * math.cos(ra), 1575 + r1 * 0.55 * math.sin(ra))], w=1.4, amp=0.5)

    # --- the thought bubbles, drifting up
    for i, (bx, by, r, sym) in enumerate(((250, 470, 120, "?"), (420, 330, 95, "chat"), (165, 720, 82, "cross"),
                                          (360, 640, 52, None), (450, 790, 26, None), (500, 850, 15, None))):
        dy = 14 * math.sin(t * 2 * math.pi / 3 + i * 1.3)
        dx = 6 * math.sin(t * 2 * math.pi / 4 + i)
        bubble(pen, bx + dx, by + dy, r, sym)

    # the scratchboard's rough edge: tiny gaps in the white
    a = np.asarray(img, np.float32)
    noise = np.random.default_rng(7 + variant).random(a.shape)
    a[(noise < 0.08)] *= 0.35
    img = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    return img.resize((W, H), Image.LANCZOS)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "still":
        draw(0, 0.0).save(OUT / "still.png")
        return
    frames = OUT / "frames"
    frames.mkdir(exist_ok=True)
    for f in range(FPS * SECONDS):
        draw((f // 3) % 3, f / FPS).save(frames / f"{f:04d}.png")  # a new drawing every 3 frames: 8 a second
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(OUT / "test_dessin.mp4")], check=True)


if __name__ == "__main__":
    main()
