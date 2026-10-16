"""Tony's testimony, episode 1, v8: animated the way of the reel Tony sent as a model.

There, every scene is a drawing that holds: only a few things move in it (eyes, a mouth, a hand, bubbles,
objects), and the next scene comes up from below, as when you scroll a feed (or the camera dives into
something, or a black hand sweeps across). So here: one drawing per phrase, in the flat chalk caricature of
v7 (tools/cartoon.py); the others' words in white bubbles, written by hand; scenes that scroll by; a dive into
his glasses to the classroom; a black hand that sweeps it away and leaves the white report card, where the
teacher's red pen writes. The captions: small hand-written capitals at the top, word by word.
Usage: python3 tools/episode1_v8.py [--until s] [t ...]  -> renders/episode1_v8_opening.mp4, or stills
"""
import math
import subprocess
import sys
import tempfile
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

import cartoon as ct
import draw_test as dt
import episode1_v7 as v7  # the timeline, the classroom, the report card, the pen's draw-on (its import patches it)
import ink
import letters
from episode1_v7 import (DRAWINGS, FPS, L, LINES, PHONE, POCKET, QC, Q_DESK, T_CLOSE, T_MATES, T_TEACH, WPS, back, bump, cam, card,
                         classroom, clip01, drawing, ease, ein, eout, kf, lerp, lerp2, seg, sweat, text_strokes)
from rig import Canvas

ROOT = Path(__file__).resolve().parents[1]
W, H, S = 1080, 1920, dt.S
_line = v7._line
SCROLL = 0.42  # a scroll from one scene to the next
END = L[10]


def pose(**k):
    return v7.tony_pose(**k)


def blink(t, every=3.1, phase=0.0):
    return bump((t + phase) % every, 0.0, 0.25)


def crc(s):
    return zlib.crc32(s.encode()) % 997


def write(cv, key, strokes, p=1.0, w=3.0, fill=255, amp=0.5, layer="white"):
    """Strokes written to progress p, white (or black: fill=0, on something white)."""
    if p <= 0:
        return None
    part, tip = letters.written(strokes, p)
    pen = cv.pen(key, layer)
    for s_ in part:
        if len(s_) > 1:
            _line(pen, s_, w, amp, fill)
        elif len(s_) == 1:
            cv.disc(s_[0][0], s_[0][1], w * 0.55, fill, layer)
    return tip


def say(cv, key, cx, cy, text, tail, scale=1.0, size=34, p=1.0, dots=0, inside=None):
    """Someone's words: a white bubble, rough-edged, its tail toward who says them, the words in black capitals;
    inside: the (left, right) the bubble must stay within (the world, as the camera sees it)."""
    if scale <= 0.03:
        return
    st, wd = letters.layout(text, "futural", size, hand=1.1, seed=crc(text)) if text else ([], size * 2.2)
    if inside is not None:
        half = (wd + size * 1.9) / 2
        cx = min(max(cx, inside[0] + half), inside[1] - half)
    w, h = (wd + size * 1.9) * scale, size * 2.5 * scale
    rng = cv.rng(key + "edge")
    ring = [(cx + (w / 2) * math.cos(a) * (1 + rng.normal(0, 0.012)), cy + (h / 2) * math.sin(a) * (1 + rng.normal(0, 0.02)))
            for a in np.linspace(0, 2 * math.pi, 60, endpoint=False)]
    ang = math.atan2(tail[1] - cy, tail[0] - cx)
    b0 = (cx + w * 0.34 * math.cos(ang - 0.3), cy + h * 0.34 * math.sin(ang - 0.3))
    b1 = (cx + w * 0.34 * math.cos(ang + 0.3), cy + h * 0.34 * math.sin(ang + 0.3))
    tl = (cx + (tail[0] - cx) * scale, cy + (tail[1] - cy) * scale)
    cv.fill(ring, 255)
    cv.fill([b0, tl, b1], 255)
    if text:
        x0 = cx - wd * scale / 2
        y0 = cy + size * scale / 2
        write(cv, key + "t", [[(x0 + a * scale, y0 + b * scale) for a, b in s_] for s_ in st], p, w=3.4 * scale, fill=0, amp=0.4)
    for i in range(dots):
        cv.disc(cx - w * 0.2 + i * w * 0.2, cy, 8 * scale, 0)


def halo(cv, key, x, y, r0, r1, n=70):
    """Short strokes all round something (a light, a spotlight)."""
    pen = cv.pen(key)
    for a in np.linspace(0, 2 * math.pi, n, endpoint=False):
        a += pen.rng.uniform(-0.03, 0.03)
        rr = r0 + (r1 - r0) * pen.rng.uniform(0.35, 1.0)
        pen.line([(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + rr * math.cos(a), y + rr * math.sin(a))], w=1.4, amp=0.4)


# --- the scenes: each draws itself at time t (variant v) on a canvas, with its own camera
def s_phone(cv, t, v):
    """« J'ai créé un réseau social… alors que j'ose même pas parler aux gens. »
    His phone, RISE drawing itself on it; the camera goes up to him; everyone else's words pop up round him."""
    up = ease(seg(t, L[1] - 0.15, L[1] + 0.5))
    z = math.exp(lerp(math.log(3.1), math.log(1.12), up))
    c = lerp2((PHONE["cx"], PHONE["cy"] - 10), (540.0, 930.0), up)
    seen = (540.0 - 500 / 1.12, 540.0 + 500 / 1.12)  # what the camera sees across, once up
    T0 = L[1] + 0.65  # the others start talking
    P = pose()
    P["breath"] = 0.5 + 0.5 * math.sin(t * 1.9)
    talk = seg(t, T0, T0 + 0.4)
    dart = kf(t, [(T0, 0.0), (T0 + 0.15, -0.8), (T0 + 0.7, -0.8), (T0 + 0.85, 0.8), (T0 + 1.4, 0.8), (T0 + 1.55, 0.0)], fn=lambda x: x)
    P.update(shrug=0.5 * talk, yaw=-6 * dart * talk)
    P["ex"] = dict(blink=blink(t, 3.0, 1.0), gx=dart, gy=-0.1, smile=0.35 - 0.45 * talk, worry=0.7 * talk)
    P["phone"] = dict(PHONE, turn=0.0, glow=0.6)
    P["arm_r"] = dict(wrist=(PHONE["cx"] + 10, PHONE["cy"] + 140), hand="none", elbow=(-0.4, 1), k2=0.45)
    P["arm_l"] = dict(wrist=POCKET, hand="pocket", elbow=(1, 0.3))

    def screen(cv_, fr):
        cx, cy = fr["P"](0, -0.08)
        v7.draw_rise(cv_, "r1", cx, cy, fr["w"] * 0.66, seg(t, 0.2, 1.4))
    with cam(z, c):
        with drawing(seg(t, 0.0, 0.45)):
            info = ct.draw_tony(cv, "tony", P, screen=screen, prog=seg(t, 0.0, 0.45))
        words = (("SALUT !", 230.0, 455.0, -40.0, 420.0), ("ON SORT ?", 860.0, 430.0, 1140.0, 360.0), ("TROP BIEN", 200.0, 880.0, -60.0, 930.0),
                 ("T'AS VU ?", 880.0, 820.0, 1160.0, 860.0), ("HAHA", 870.0, 1180.0, 1160.0, 1240.0))
        for k, (txt, bx, by, tx, ty) in enumerate(words):
            at = T0 + 0.18 * k
            sc = back(seg(t, at, at + 0.25)) * (1 - ein(seg(t, L[2] - 0.3, L[2] - 0.05)))
            say(cv, f"w{k}", bx, by + 4 * math.sin(t * 5 + k), txt, (tx, ty), sc, size=32, inside=seen)
        mine = back(seg(t, T0 + 1.0, T0 + 1.25)) * (1 - ein(seg(t, L[2] - 0.55, L[2] - 0.3)))
        if mine > 0.03:  # his own: three dots that never become words
            n = min(3, max(0, int((t - T0 - 1.1) * 5)))
            mouth = info["head"].pt(60.0, 100.0)
            say(cv, "mine", 735.0, 1000.0, "", mouth, mine, size=30, dots=n)


def s_hello(cv, t, v):
    """« Moi c'est Tony. »: he waves, shyly; his name, written next to him."""
    a = L[2]
    P = pose(x=600.0)
    P["breath"] = 0.5 + 0.5 * math.sin(t * 1.9)
    wave_in = back(seg(t, a + 0.1, a + 0.4))
    cyc = int((t - a) * 6) % 4  # the hand, drawn in a few positions, as by hand
    ang = (-96, -84, -72, -84)[cyc] if t > a + 0.4 else -84
    wr = lerp2((760.0, 1960.0), (930.0 + (ang + 84) * 1.2, 1150.0), wave_in)
    P["arm_l"] = dict(wrist=wr, hand="open" if wave_in > 0.4 else "pocket", ang=ang, spread=0.95, elbow=(0.25, 1.0))
    P["arm_r"] = dict(wrist=(470.0, 1960.0), hand="pocket", elbow=(-1, 0.3))
    P["ex"] = dict(blink=blink(t, 2.6, 0.4), smile=0.55, brow=0.4, gx=0.0, gy=0.0)
    P.update(roll=-4.0, shrug=0.35)
    with cam(1.25, (590.0, 880.0)):
        hd = ct.head_of(P)
        halo(cv, "halo", hd.cx, hd.cy - 20, 330, 420, 90)
        ct.draw_tony(cv, "tony2", P)
        p = seg(t, a + 0.25, a + 0.85)
        write(cv, "name", text_strokes("TONY", "futural", 96, 195.0, 1185.0, hand=1.0, seed=4), p, w=7.0)
        v7.arrow(cv, "arr", [(300, 1080), (330, 990), (385, 930)], seg(t, a + 0.75, a + 1.05), w=4.0)


GROUP = [(560.0, 1010.0, ct.ADULT_W, 26, 0.0), (775.0, 990.0, ct.ADULT_B, -4, 1.7), (975.0, 1015.0, ct.ADULT_M, -28, 3.1)]


def s_party(cv, t, v):
    """« Et je suis le genre de personne qui ose pas aller vers les autres. »
    The others, together, laughing; him at the edge, his phone in his hand; he goes, he stops, he goes back."""
    a = L[3]
    pen = cv.pen("garland")
    with cam(1.0, (540.0, 960.0)):
        # a string of lights across the room
        gl = [(x, 360 + 50 * math.sin(x / 170)) for x in np.linspace(-20, 1100, 40)]
        pen.line(gl, w=2.4)
        for k, x in enumerate(np.linspace(30, 1060, 9)):
            y = 360 + 50 * math.sin(x / 170) + 22
            on = 1.0 if (int(t * 4) + k) % 3 else 0.7
            pen.line([(x - 9, y - 12), (x, y + 10), (x + 9, y - 12), (x - 9, y - 12)], w=2.4)
            halo(cv, f"b{k}{int(on * 10)}", x, y, 20, 20 + 26 * on, 16)
        for k, (x, y, face, yaw, ph) in enumerate(GROUP):
            laugh = bump((t + ph * 0.37) % 2.4, 0.0, 0.9)
            talk = max(0.0, math.sin(t * 8 + ph * 2)) * (1 - laugh)
            G = pose(x=x, y=y - 12 * laugh, s=0.98, face=face, head_k=1.12, yaw=yaw + 5 * math.sin(t * 1.3 + ph), pitch=8 * laugh, roll=5 * math.sin(t * 2 + ph),
                     outfit="shirt" if k == 1 else "tee", cloth=1.2)
            G["ex"] = dict(open=0.32 * talk + 0.35 * laugh, smile=0.6 + 0.4 * laugh, squint=0.9 * laugh, gx=0.6 if yaw > 0 else -0.6, blink=blink(t, 2.9, ph))
            cup_y = y + 330 - 40 * bump((t + ph * 0.5) % 4.0, 0.0, 1.0)
            G["arm_r"] = dict(wrist=(x - 70, cup_y + 60), hand="fist", ang=-75, elbow=(-1, 0.6), k2=0.6)
            G["arm_l"] = dict(wrist=(x + 125, y + 560), hand="pocket", elbow=(1, 0.4))
            ct.draw_tony(cv, f"g{k}", G)
            cup = [(x - 98, cup_y - 44), (x - 42, cup_y - 44), (x - 48, cup_y + 34), (x - 92, cup_y + 34)]
            cv.solid(cup)
            cv.pen(f"cup{k}").line(cup + cup[:1], w=3.0)
            cv.pen(f"cup{k}").hatch(cup, 80, 9, w=1.3)
        sc = back(seg(t, a + 0.7, a + 0.95)) * (1 - ein(seg(t, L[4] - 0.35, L[4] - 0.1)))
        say(cv, "haha", 700.0, 560.0, "HAHAHA !", (760.0, 690.0), sc, size=38)
        sc2 = back(seg(t, a + 2.2, a + 2.45)) * (1 - ein(seg(t, L[4] - 0.35, L[4] - 0.1)))
        say(cv, "trop", 905.0, 690.0, "TROP DRÔLE", (960.0, 800.0), sc2, size=34)
        # him, in front, at the edge: he looks at them, takes a step, stops, steps back
        step = back(seg(t, a + 1.5, a + 1.9), 1.2) * (1 - ease(seg(t, a + 3.2, a + 3.6)))
        stuck = seg(t, a + 2.4, a + 2.6) * (1 - seg(t, a + 3.3, a + 3.6))
        down = seg(t, a + 3.5, a + 3.9)
        P = pose(x=120.0 + 60 * step, y=1260.0, s=1.6)
        P["breath"] = 0.5 + 0.5 * math.sin(t * 2.2)
        P.update(yaw=22 * (1 - down) - 8 * down, pitch=-12 * down, lean=7 * step, shrug=0.4 + 0.3 * stuck)
        P["ex"] = dict(blink=blink(t, 2.7, 0.8), gx=0.85 * (1 - down), gy=0.85 * down, smile=0.25 * step - 0.3 * stuck, worry=0.3 + 0.7 * stuck, brow=0.2 * stuck)
        P["arm_r"] = dict(wrist=(150.0 + 60 * step, 1720.0), hand="fist", ang=-60, elbow=(-1, 0.6), k2=0.6)
        P["arm_l"] = dict(wrist=(360.0 + 70 * step, 1600.0 - 90 * step * (1 - stuck)), hand="open" if step > 0.5 else "fist", ang=-40, spread=0.6,
                          curl=0.4, elbow=(0.6, 1.0))
        info = ct.draw_tony(cv, "tonyp", P)
        sw = seg(t, a + 2.45, a + 2.65) * (1 - seg(t, a + 3.4, a + 3.6))
        if sw > 0:
            sx, sy = info["head"].pt(165.0, -100.0)
            sweat(cv, "sweat", sx, sy + 50 * seg(t, a + 2.65, a + 3.4), 2.2, sw)


def s_question(cv, t, v):
    """« Qui ose pas poser de questions. »: in a group, his hand half up; a « ? »; it falls back down."""
    a = L[4]
    r_up = back(seg(t, a + 0.25, a + 0.6), 1.4) * (1 - ein(seg(t, a + 1.45, a + 1.65)))
    P = pose(x=560.0)
    P["breath"] = 0.5 + 0.5 * math.sin(t * 2.0)
    P["arm_l"] = dict(wrist=lerp2((760.0, 1960.0), (930.0, 1120.0), r_up), hand="open" if r_up > 0.4 else "pocket", ang=-86 + 4 * math.sin(t * 30) * r_up,
                      spread=0.5, curl=0.45, elbow=(0.3, 1.0))
    P["arm_r"] = dict(wrist=(470.0, 1960.0), hand="pocket", elbow=(-1, 0.3))
    P.update(shrug=0.3 + 0.3 * r_up, pitch=6 * r_up)
    P["ex"] = dict(blink=blink(t, 2.8, 0.2), gy=-0.6 * r_up + 0.6 * seg(t, a + 1.5, a + 1.8), gx=0.35 * r_up, worry=0.5 + 0.4 * r_up, smile=-0.1)
    with cam(1.2, (600.0, 960.0)):
        ct.draw_tony(cv, "tonyq", P)
        q = back(seg(t, a + 0.5, a + 0.8)) * (1 - ein(seg(t, a + 1.5, a + 1.8)))
        fall = ein(seg(t, a + 1.5, a + 2.0))
        say(cv, "q", 940.0, 760.0 + 500 * fall, "?", (930.0, 900.0 + 500 * fall), q, size=64)
        # the backs of the others' heads, in front: he is in a group
        for k, x in enumerate((90.0, 330.0, 790.0, 1020.0)):
            hx, hy = x, 1760.0 + 30 * (k % 2)
            head = [(hx + 120 * math.cos(u), hy + 140 * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 50)]
            cv.solid(head + [(hx + 260, 2100), (hx - 260, 2100)])
            pen = cv.pen(f"back{k}")
            pen.line(head, w=4.0)
            pen.hatch(head, 80 + 20 * k, 13, w=1.5)
            pen.line([(hx - 250, 2000), (hx - 150, 1850), (hx - 100, 1830)], w=4.0)
            pen.line([(hx + 250, 2000), (hx + 150, 1850), (hx + 100, 1830)], w=4.0)


def s_babble(cv, t, v):
    """« Peut-être par peur de dire n'importe quoi… »: he opens his mouth, a tangle comes out; crumpled, it drops."""
    a = L[5]
    T_SAY, T_CRUMPLE, T_FALL = a + 0.25, a + 1.35, a + 1.8
    say_ = seg(t, T_SAY - 0.1, T_SAY + 0.1) * (1 - seg(t, T_CRUMPLE - 0.1, T_CRUMPLE + 0.1))
    P = pose()
    P["breath"] = 0.5 + 0.5 * math.sin(t * 2.0)
    P["arm_l"] = dict(wrist=POCKET, hand="pocket", elbow=(1, 0.3))
    P["arm_r"] = dict(wrist=(380.0, 1960.0), hand="pocket", elbow=(-1, 0.3))
    fall_look = seg(t, T_FALL, T_FALL + 0.3)
    P["ex"] = dict(blink=blink(t, 3.3, 0.6), open=0.45 * say_ * (0.75 + 0.25 * math.sin(t * 19)), gx=0.4 * say_ - 0.2 * fall_look, gy=-0.4 * say_ + 0.9 * fall_look,
                   worry=0.3 + 0.5 * seg(t, T_CRUMPLE, T_CRUMPLE + 0.2), smile=0.0)
    P.update(shrug=0.3, pitch=-6 * fall_look)
    with cam(1.55, (560.0, 830.0)):
        info = ct.draw_tony(cv, "tonyb", P)
        if T_SAY - 0.05 < t < T_FALL + 1.0:
            mouth = info["head"].pt(46.0, 106.0)
            grow = back(seg(t, T_SAY, T_SAY + 0.45))
            cr = ease(seg(t, T_CRUMPLE, T_FALL))
            bx, by = mouth[0] + 180 * grow, mouth[1] - 230 * grow
            if t > T_FALL:
                f_ = t - T_FALL
                bx += 120 * f_
                by += 0.5 * 3600 * f_ * f_
            rng = cv.rng("crumple")
            n = 40
            ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
            rr = 1 + rng.uniform(-1, 1, n) * 0.24 * cr
            rw = (170 * (1 - cr) + 46 * cr) * grow
            rh = (125 * (1 - cr) + 44 * cr) * grow
            ring = [(bx + rw * r_ * math.cos(q), by + rh * r_ * math.sin(q)) for q, r_ in zip(ang, rr)]
            cv.fill(ring, 255)
            if cr < 0.05:
                cv.fill([(bx - rw * 0.55, by + rh * 0.55), (mouth[0] + 10, mouth[1] - 6), (bx - rw * 0.2, by + rh * 0.85)], 255)
            tg = cv.rng("tangle")
            pts = [(bx + rw * 0.6 * math.cos(q) * tg.uniform(0.3, 1), by + rh * 0.55 * math.sin(q * 1.7) * tg.uniform(0.3, 1)) for q in np.linspace(0, 9 * math.pi, 46)]
            with drawing(seg(t, T_SAY + 0.12, T_CRUMPLE - 0.1)):
                cv.pen("tangle").line(ink.smooth(pts, n=5), w=3.0 * (1 - 0.5 * cr), amp=1.0, fill=0)
            for k in range(int(12 * cr)):  # its creases
                a0 = tg.uniform(0, 2 * math.pi)
                cv.pen("crease").line([(bx + rw * 0.15 * math.cos(a0), by + rh * 0.15 * math.sin(a0)), (bx + rw * 0.95 * math.cos(a0 + 0.5), by + rh * 0.95 * math.sin(a0 + 0.5))],
                                      w=2.2, amp=0.6, fill=0)


TYPED = "Désolé de te déranger…"


def s_typing(cv, t, v):
    """« …ou peut-être par peur de déranger. »: on his phone, he writes « Désolé de te déranger… », and rubs it out."""
    a = L[6]
    T_TYPE, T_ERASE = a + 0.25, a + 1.45
    n = len(TYPED)
    k = int(n * seg(t, T_TYPE, T_TYPE + 1.0))
    if t > T_ERASE:
        k = int(n * (1 - seg(t, T_ERASE, T_ERASE + 0.6)))
    ph = dict(cx=540.0, cy=1000.0, w=560.0, h=1120.0, angle=-3.0)
    with cam(1.0, (540.0, 960.0)):
        def screen(cv_, fr):
            P_ = fr["P"]
            pen = cv_.pen("ui")
            # a conversation: someone's round picture, their messages on the left; the keyboard below
            cx, cy = P_(-0.62, -0.78)
            pen.line([(cx + 34 * math.cos(u), cy + 34 * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 30)], w=2.6)
            pen.line([P_(-0.4, -0.82), P_(0.1, -0.82)], w=2.6)
            pen.line([P_(-0.4, -0.74), P_(-0.05, -0.74)], w=1.8)
            pen.line([P_(-0.95, -0.68), P_(0.95, -0.68)], w=1.6)
            for j, (y0, wd) in enumerate(((-0.58, 0.9), (-0.42, 0.65))):
                box = v7.rig.rounded_rect(*P_(-0.88 + wd / 2, y0), wd * fr["w"] / 2, 0.11 * fr["h"] / 2, 24, fr["angle"])
                pen.line(box + box[:1], w=2.4)
                pen.line([P_(-0.8, y0 - 0.01), P_(-0.88 + wd - 0.12, y0 - 0.01)], w=1.6, amp=1.0)
            # the field where he writes, above the keyboard
            field = v7.rig.rounded_rect(*P_(-0.08, 0.13), 1.55 * fr["w"] / 2, 0.1 * fr["h"] / 2, 30, fr["angle"])
            cv_.solid(field)
            pen.line(field + field[:1], w=2.6)
            x0, y0 = P_(-0.78, 0.155)
            if k > 0:
                st = text_strokes(TYPED[:k], "futural", 30, x0, y0, hand=0.6, seed=11)
                write(cv_, "typed", st, 1.0, w=2.8)
                cx_ = max(x for s_ in st for x, _ in s_) + 8
            else:
                cx_ = x0
            if int(t * 4) % 2 == 0:
                pen.line([(cx_, y0 - 30), (cx_, y0 + 4)], w=2.8, amp=0.2)
            sx, sy = P_(0.82, 0.13)  # the send arrow, never pressed
            pen.line([(sx - 16, sy + 14), (sx + 18, sy), (sx - 16, sy - 14), (sx - 6, sy), (sx - 16, sy + 14)], w=2.6)
            # the keyboard: three rows of keys, the one he taps lit
            keys = []
            for r, (n_k, off) in enumerate(((10, 0.0), (9, 0.05), (7, 0.15))):
                for i in range(n_k):
                    x = -0.92 + off + i * (1.84 - 2 * off) / n_k + (1.84 - 2 * off) / n_k / 2
                    keys.append((x, 0.36 + r * 0.17))
            hit = (int(t * 12) * 7) % len(keys) if T_TYPE < t < T_ERASE + 0.6 else -1
            for i, (x, y) in enumerate(keys):
                kb = v7.rig.rounded_rect(*P_(x, y), 0.15 * fr["w"] / 2, 0.13 * fr["h"] / 2, 10, fr["angle"])
                if i == hit:
                    cv_.fill(kb, 255)
                else:
                    pen.line(kb + kb[:1], w=1.6)
            sb = v7.rig.rounded_rect(*P_(0.0, 0.87), 0.9 * fr["w"] / 2, 0.12 * fr["h"] / 2, 12, fr["angle"])
            pen.line(sb + sb[:1], w=1.6)
        v7.rig.draw_phone(cv, "bigph", ph["cx"], ph["cy"], ph["w"], ph["h"], ph["angle"], 0.0, screen, 0.5)
        # his thumb, over the keys
        tap = math.sin(t * 24) * (1 if T_TYPE < t < T_ERASE + 0.6 else 0)
        tx, ty = 690.0 + 60 * math.sin(t * 5.3), 1330.0 + 40 * math.sin(t * 3.1) + 12 * tap
        poly, _ = ct.finger_outline((tx + 260, ty + 330), math.atan2(-330, -260), [230.0, 170.0], [120.0, 112.0, 100.0], [0.0, -0.25])
        ct.shape(cv, cv.pen("thumb"), poly, w=4.2)
        cv.pen("thumb").line([(tx + 12, ty + 30), (tx + 40, ty + 10)], w=2.2)


def s_glasses(cv, t, v, z=1.0, c=(540.0, 900.0), draw=True):
    """« Depuis tout jeune… »: his face, looking at us (the camera will go into his lens)."""
    P = pose()
    P["breath"] = 0.5 + 0.5 * math.sin(t * 1.8)
    P["arm_l"] = dict(wrist=POCKET, hand="pocket", elbow=(1, 0.3))
    P["arm_r"] = dict(wrist=(380.0, 1960.0), hand="pocket", elbow=(-1, 0.3))
    P["ex"] = dict(blink=blink(t, 3.4, 0.9) if t < L[7] + 0.2 else 0.0, gy=-0.1, worry=0.65, smile=-0.15)
    P.update(shrug=0.35, pitch=3.0)
    if draw:
        with cam(z, c):
            ct.draw_tony(cv, "tonyg", P)
    return P


LENS_R = 1500.0
T_LENS = (L[7] + 0.35, L[7] + 1.6)


def lens_picture(t, v):
    """The camera going into his lens: him outside it, the classroom inside it, drawing itself."""
    P = s_glasses(None, t, v, draw=False)
    lp = np.asarray(ct.lens_poly(P, -1, n=160))
    lc_w = lp.mean(axis=0)
    u = seg(t, *T_LENS)
    z0, c0 = 1.6, (560.0, 820.0)
    z = math.exp(lerp(math.log(z0), math.log(32.0), ease(u) ** 1.3))
    c = lerp2(c0, tuple(lc_w), eout(min(1.0, u * 1.7)))
    cv = Canvas(v)
    with cam(z, c):
        ls = ink.to_screen(lp)
        covered = all(v7.cv_inside(ls, q) for q in ((0, 0), (W, 0), (0, H), (W, H)))
        if not covered:
            s_glasses(cv, t, v, z, c)
    out = ct.picture(cv)
    lc = ls.mean(axis=0)
    r = float(np.mean(np.hypot(*(ls - lc).T)))
    if r < 30:
        return out
    cc = Canvas(v)
    with cam(r / LENS_R, (540.0, 1000.0), tuple(lc)):
        classroom(cc, t, seg(r, 30, 420))
    inside = ct.picture(cc)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([tuple(q) for q in (ls - lc) * (1 - 3.0 / max(r, 1)) + lc], fill=255)
    out.paste(inside, (0, 0), m)
    return out


def class_camera(t):
    P = s_glasses(None, T_LENS[1], 0, draw=False)
    lp = np.asarray(ct.lens_poly(P, -1, n=160))
    r_world = float(np.mean(np.hypot(*(lp - lp.mean(axis=0)).T)))
    z_end = math.exp(lerp(math.log(1.6), math.log(32.0), 1.0))
    z0 = r_world * z_end / LENS_R
    u = ease(seg(t, T_LENS[1], T_LENS[1] + 0.6))
    return lerp(z0, 1.0, u), lerp2((540.0, 1000.0), (540.0, 960.0), u)


# --- the end: the hands of those close to him; a black hand sweeps it all away; the report card, white
T_HANDS = L[9] + 0.1
T_WIPE = (L[9] + 1.25, L[9] + 1.75)
T_WRITE = (T_WIPE[1] + 0.35, T_WIPE[1] + 2.6)


def big_hand(cv, key, wrist, ang, L_, side=1, spread=0.7):
    """A hand of someone bigger: a black hand, outlined, its fingers spread."""
    ct.hand_open(cv, key, wrist, ang, L_, side, spread, 0.15)


def class_picture(t, v):
    cv = Canvas(v)
    z, c = class_camera(t)
    with cam(z, c):
        classroom(cv, t, 1.0)
        # the hands of grown-ups, coming down on him from above
        hp = eout(seg(t, T_HANDS, T_HANDS + 0.5))
        if hp > 0:
            big_hand(cv, "gh1", (210.0, -260.0 + 560 * hp), 62, 520, 1)
            big_hand(cv, "gh2", (900.0, -300.0 + 600 * eout(seg(t, T_HANDS + 0.2, T_HANDS + 0.7))), 112, 560, -1)
    return ct.picture(cv)


def paper_picture(t, v):
    """The report card, white, the teacher's red pen writing on it (drawn white on black, then turned over)."""
    cv = Canvas(v)
    with cam():
        tip = card(cv, QC, seg(t, *T_WRITE), detail=1.0)
        hand_in = eout(seg(t, T_WRITE[0] - 0.35, T_WRITE[0]))
        hand_out = ein(seg(t, T_WRITE[1] + 0.15, T_WRITE[1] + 0.5))
        if hand_in > 0 and hand_out < 1:
            if tip is None:
                tip = v7.qpt(QC, 70, 690)
            off = (1 - hand_in) * 700 + hand_out * 800
            v7.pen_hand(cv, (tip[0] + off * 0.6, tip[1] + off), t)
    w = ct.grain(cv.white, v).resize((W, H), Image.LANCZOS)
    w = ImageOps.invert(w)
    rgb = Image.merge("RGB", (w, w, w))
    red = cv.inks["red"]
    if red is not None and red.getbbox():
        rgb.paste((214, 30, 30), (0, 0), ct.grain(red, v).resize((W, H), Image.LANCZOS))
    return rgb


class MaskCanvas(Canvas):
    """A canvas where what would hide things is white: what it draws is a shape's whole silhouette."""

    def solid(self, poly, fill=0):
        super().fill(poly, 255)


def wipe_picture(t, v):
    """A huge black hand sweeps across from the right, wiping the classroom away: behind it, the white report card."""
    u = ease(seg(t, *T_WIPE))
    before = class_picture(t, v)
    after = paper_picture(t, v)
    x_tip = W + 80 - (W + 1500) * u  # where its fingertips are
    m = Image.new("L", (W, H), 0)
    if x_tip + 900 < W:
        ImageDraw.Draw(m).rectangle([int(x_tip + 900), 0, W, H], fill=255)
    out = before.copy()
    out.paste(after, (0, 0), m)

    def hand(c):
        with cam():
            big_hand(c, "wipe", (x_tip + 1180, 1050.0), 186, 1250, 1, spread=0.55)
    mc = MaskCanvas(v)
    hand(mc)
    lc = Canvas(v)
    hand(lc)
    out.paste((0, 0, 0), (0, 0), mc.white.resize((W, H), Image.LANCZOS))
    out.paste((255, 255, 255), (0, 0), ct.grain(lc.white, v).resize((W, H), Image.LANCZOS))
    return out


# --- the order of things, and the scroll from one scene to the next
SCENES = [(0.0, s_phone), (L[2], s_hello), (L[3], s_party), (L[4], s_question), (L[5], s_babble), (L[6], s_typing), (L[7], None)]


def scene_picture(i, t, v):
    fn = SCENES[i][1]
    if fn is None:
        return glasses_or_class(t, v)
    cv = Canvas(v)
    fn(cv, t, v)
    return ct.picture(cv)


def glasses_or_class(t, v):
    if t < T_LENS[0]:
        cv = Canvas(v)
        s_glasses(cv, t, v, 1.6, (560.0, 820.0))
        return ct.picture(cv)
    if t < T_LENS[1]:
        return lens_picture(t, v)
    if t < T_WIPE[0]:
        return class_picture(t, v)
    if t < T_WIPE[1] + 0.05:
        return wipe_picture(t, v)
    return paper_picture(t, v)


def picture(t, v):
    starts = [s for s, _ in SCENES]
    for j in range(1, len(starts)):  # scrolling from one scene up to the next (as in a feed)?
        u = seg(t, starts[j] - 0.12, starts[j] - 0.12 + SCROLL)
        if 0 < u < 1:
            e = ease(u)
            A = scene_picture(j - 1, t, v)
            B = scene_picture(j, t, v)
            out = Image.new("RGB", (W, H))
            dy = int(round(H * e))
            out.paste(A, (0, -dy))
            out.paste(B, (0, H - dy))
            return out
    i = max(k for k, s in enumerate(starts) if s - 0.12 + SCROLL <= t + 1e-9 or k == 0)
    return scene_picture(i, t, v)


# --- the captions: small capitals, written by hand, word by word
CAP = dict(font="futural", size=36, line=58, top=178, width=900, w=4.2, edge=9.0)
_caps = {}


def caption(t, v):
    line = next((l for l in LINES if l["t0"] <= t < l["t1"]), None)
    if line is None:
        return None
    said = (t - line["t0"]) * WPS
    text = line["text"].upper()
    words = text.split(" ")
    k = min(len(words), 1 + int(said))
    key = (text, k, v)
    if key in _caps:
        return _caps[key]
    edge, white = Canvas(v), Canvas(v)
    lines = letters.wrap(text, CAP["font"], CAP["size"], CAP["width"])
    n = 0
    with cam():
        for i, ln in enumerate(lines):
            ws = ln.split(" ")
            gap = CAP["size"] * 0.12
            full_w = letters.width(ln, CAP["font"], CAP["size"]) + gap * len(ln)
            x = 540 - full_w / 2
            y = CAP["top"] + i * CAP["line"]
            for j, w_ in enumerate(ws):
                if n >= k:
                    break
                st = []
                xx = x
                for ch in w_:  # spaced capitals
                    cs = text_strokes(ch, CAP["font"], CAP["size"], xx, y, hand=0.9, seed=crc(w_) + len(st))
                    st += cs
                    xx += letters.width(ch, CAP["font"], CAP["size"]) + gap
                write(edge, f"e{i}{j}", st, 1.0, w=CAP["w"] + CAP["edge"], amp=0.4)
                write(white, f"c{i}{j}", st, 1.0, w=CAP["w"], amp=0.4)
                x = xx + letters.width(" ", CAP["font"], CAP["size"]) + gap
                n += 1
    out = (ct.grain(edge.white, v).resize((W, H), Image.LANCZOS), ct.grain(white.white, v).resize((W, H), Image.LANCZOS))
    _caps[key] = out
    return out


def frame_at(t):
    v = int(t * DRAWINGS) % 3
    pic = picture(t, v)
    cap = caption(t, v)
    if cap is not None:
        on_paper = t >= T_WIPE[1]
        if on_paper:  # on the white paper: black words
            pic.paste((255, 255, 255), (0, 0), cap[0])
            pic.paste((0, 0, 0), (0, 0), cap[1])
        else:
            pic.paste((0, 0, 0), (0, 0), cap[0])
            pic.paste((255, 255, 255), (0, 0), cap[1])
    return pic


def _render(args):
    g, d = args
    frame_at(g / DRAWINGS).save(f"{d}/{g:05d}.png")
    return g


def main(until=END):
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    until = min(until, END)
    name = "episode1_v8_opening.mp4" if until >= END else f"episode1_v8_0-{until:g}s.mp4"
    n = int(until * DRAWINGS)
    with tempfile.TemporaryDirectory() as d:
        with Pool(4) as pool:
            for i, _ in enumerate(pool.imap_unordered(_render, [(g, d) for g in range(n)], chunksize=2)):
                if i % 48 == 0:
                    print(f"{i}/{n}", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(DRAWINGS), "-i", f"{d}/%05d.png", "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                        "-shortest", "-movflags", "+faststart", str(out / name)], check=True)
    print(out / name, f"{until:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--until":
        main(float(sys.argv[2]))
    elif len(sys.argv) > 1:
        for s_ in sys.argv[1:]:
            tt = int(float(s_) * DRAWINGS) / DRAWINGS
            frame_at(tt).save(ROOT / f"still_{s_}.png")
    else:
        main()
