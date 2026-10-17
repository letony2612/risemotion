"""Tony's film, on his voice (tools/voice.py: assets/voice/voice.wav, and take.json with every word's time), in the
drawing he validated (sketch.py), played the way the reel he sent plays: held drawings redrawn twelve times a second
so the ink boils a little, a few things moving at once, the scenes joined by camera moves rather than cuts (a scroll
to the next page where the place changes). What is random in a drawing (where the hairs, the rays, the tangle are)
stays put from one drawing to the next; only the hand that traces them changes. Every move is keyed to his words.
It opens on what goes on in his head when he wants to reach out to someone, drawn as his phone's alert (« Demander de
la prière ? Tu risques de déranger. »), « Annuler » circled; near the end the same alert is on RISE, and this time
« Demander » gets circled. It closes on him at his table, smiling a little, and RISE's logo. The line he is saying is
written at the top, word by word as he says it.
Usage: python3 tools/film.py [--until SECONDS]  -> renders/film_v4.mp4
       python3 tools/film.py T1 T2 ...         -> renders/film_T.png (the drawing at those times)
"""
import json
import math
import subprocess
import sys
import tempfile
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

import letters
from sketch import (S, H, W, Hand, alert, back_table, big_phone, body, bricks, bubble, bulletin, chair, church, dashes, finish, framed,
                    head, loop_pts, person, phone_on_table, rise_logo, scrawl, speech, table)

ROOT = Path(__file__).resolve().parents[1]
FPS, DRAWINGS = 24, 12  # twelve drawings a second, each held two frames
VOICE = ROOT / "assets" / "voice"
TAKE = json.loads((VOICE / "take.json").read_text())
LINES = [line["text"] for line in TAKE["lines"]]
WORDS = [line["words"] for line in TAKE["lines"]]
T = [line["start"] for line in TAKE["lines"]] + [TAKE["duration"]]  # when each line starts; T[-1]: the end of his voice
END = TAKE["duration"] + 1.7  # and RISE's logo, held after his last word
CAP = dict(font="futural", size=32, line=52, top=128, width=960)


def said(i, start):
    """When he says the word of line i that begins with `start`."""
    for w in WORDS[i]:
        if w["w"].lower().lstrip("…").startswith(start.lower()):
            return w["start"]
    raise KeyError((i, start))


# where the camera is on his page: zoom, and where his head lands (it is at 620, 962 in the drawing)
BASE, CORNER, GROUP = (1.0, 620.0, 962.0), (0.42, 790.0, 1481.0), (0.92, 330.0, 1143.0)
LOW, WALL, FAR = (0.42, 540.0, 1560.0), (0.75, 560.0, 1180.0), (0.3, 260.0, 1640.0)
ALERT = (300.0, 385.0)  # the alert in his head: where it is on the page, over him


def close(z):
    """Close on the alert, at zoom z: it fills the page, a little above the middle."""
    return (z, 540.0 + (620.0 - ALERT[0]) * z, 900.0 + (962.0 - ALERT[1]) * z)


CIRCLED = (said(1, "Moi"), said(1, "Moi") + 0.55)  # « Annuler » circled
PULL = (T[2] - 0.1, said(2, "j'ai") + 0.3)  # the camera pulls back: it is a thought over him
LIGHT = (said(2, "réseau") - 0.05, said(2, "réseau") + 0.3)  # his phone lights up
CAMERA = [(0.0, close(2.0)), (PULL[0], close(2.12)), (PULL[1], BASE),
          (T[4], BASE), (T[4] + 0.8, CORNER), (T[5], CORNER), (T[5] + 0.55, BASE),  # « renfermé »: far off, in a corner
          (T[7], BASE), (T[7] + 0.7, GROUP),  # « …ou par peur de déranger »: the others, at their table
          (T[8] - 0.1, GROUP), (T[8] + 0.6, LOW),  # « rabaissé »: small, under them
          (T[10], LOW), (T[10] + 0.8, WALL),  # « …des barrières »: his wall
          (T[12], WALL), (T[12] + 0.9, FAR)]  # « Aller vers les gens… »: far from them
# his face: where he looks (across, down), how open his lids are, his smile, his worry
q_up = said(5, "n'osait")
FACE = [(0.0, (0.0, 1.0, 12.0, 0.0, 0.0)), (T[3] + 0.05, (0.0, 1.0, 12.0, 0.0, 0.0)), (T[3] + 0.3, (0.12, -0.3, 13.5, 0.0, 0.0)),
        (T[3] + 0.45, (0.12, -0.3, 13.5, 0.0, 0.0)), (T[3] + 0.75, (0.12, -0.3, 13.5, 0.3, 0.0)), (T[4], (0.12, -0.3, 13.5, 0.3, 0.0)),
        (T[4] + 0.25, (0.0, 1.0, 12.0, 0.0, 0.1)), (T[4] + 0.7, (0.0, 1.0, 12.0, 0.0, 0.35)), (q_up, (0.0, 1.0, 12.0, 0.0, 0.35)),
        (q_up + 0.3, (0.15, -1.1, 13.0, -0.25, 0.45)), (T[6] + 0.1, (0.15, -1.1, 13.0, -0.25, 0.45)),
        (T[6] + 0.35, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[7] + 0.3, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[7] + 0.6, (0.95, -0.6, 13.0, -0.15, 0.4)),
        (T[8], (0.95, -0.6, 13.0, -0.15, 0.4)), (T[8] + 0.4, (0.0, -1.2, 13.5, -0.3, 0.7)),  # up at them
        (said(9, "amis") - 0.1, (0.0, -1.2, 13.5, -0.3, 0.7)), (said(9, "amis") + 0.15, (-0.8, -1.0, 13.5, -0.3, 0.7)),
        (said(9, "proches") - 0.1, (-0.8, -1.0, 13.5, -0.3, 0.7)), (said(9, "proches") + 0.15, (0.0, -1.2, 13.5, -0.3, 0.75)),
        (said(9, "profs") - 0.1, (0.0, -1.2, 13.5, -0.3, 0.75)), (said(9, "profs") + 0.15, (0.8, -1.0, 13.5, -0.35, 0.8)),
        (T[10] + 0.2, (0.8, -1.0, 13.5, -0.35, 0.8)), (T[10] + 0.7, (0.0, 0.8, 12.0, -0.2, 0.5)),  # down, behind his wall
        (said(11, "jugement") - 0.1, (0.0, 0.8, 12.0, -0.2, 0.5)), (said(11, "jugement") + 0.1, (-0.9, -0.3, 13.5, -0.3, 0.7)),
        (said(11, "regard") - 0.1, (-0.9, -0.3, 13.5, -0.3, 0.7)), (said(11, "regard") + 0.1, (0.9, -0.3, 13.5, -0.3, 0.7)),
        (said(11, "autres") - 0.1, (0.9, -0.3, 13.5, -0.3, 0.7)), (said(11, "autres") + 0.1, (0.0, -0.9, 13.5, -0.3, 0.7)),
        (T[12] + 0.5, (0.0, -0.9, 13.5, -0.3, 0.7)), (T[12] + 1.0, (0.7, -0.9, 12.5, -0.2, 0.5))]  # over to them, far off
BLINKS = [LIGHT[1] + 0.15, T[5] - 0.25, T[9] + 0.3, T[11] - 0.2, T[13] + 0.7, T[18] + 0.6, T[18] + 2.4]
TRAIL = [(456, 724, 12), (414, 692, 22), (345, 625, 50)]  # the first drawing's little bubbles, from his head up to a thought
GROUP_PEOPLE = [(850, 770, 0.5, "short", (-0.6, 0.2), "talk", True), (690, 800, 0.5, "long", (0.8, 0.1), "smile", False),
                (1004, 815, 0.5, "curly", (-0.9, 0.1), "smile", False)]
GIANTS = [(190, 520), (540, 430), (890, 520)]  # where they loom, over him (the same three, left to right as they sat)
JUDGES = [(120, 420, "short", True), (960, 450, "long", False), (540, 250, "curly", False)]  # « …du regard des autres »
FAR_GROUP = [(690, 704), (762, 698), (834, 704)]  # the same three, far off: at the church
SCRAWLS = [(80, 640, 260), (720, 700, 280), (160, 900, 220), (760, 940, 240)]  # the words he heard, round him
FAMILY = [(150, "short", "talk", False), (360, "long", "smile", False), (720, "curly", "smile", False), (930, "short", "talk", True)]
COMMUNITY = [(160, 1300, "long"), (920, 1300, "short"), (300, 1620, "curly")]
SCROLLS = [(T[14] - 0.35, T[14] + 0.1), (T[15] - 0.55, T[15] - 0.1), (T[18] - 0.5, T[18] - 0.05)]  # to the next page


def seg(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a)))


def ease(x):
    return x * x * (3 - 2 * x)


def pop(x):
    """Comes up a little past its size and settles (0 before, 1 once there)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def bump(t, at, d=0.35):
    """A nudge: 0, up to 1 and back to 0 over d seconds from at."""
    return math.sin(math.pi * seg(t, at, at + d)) if at <= t <= at + d else 0.0


def lerp(a, b, e):
    return a + (b - a) * e


def keyed(keys, t):
    """The value at t between keyframes (time, tuple), eased from one to the next."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, a), (tb, b) in zip(keys, keys[1:]):
        if t < tb:
            e = ease((t - ta) / (tb - ta))
            return tuple(x + (y - x) * e for x, y in zip(a, b))
    return keys[-1][1]


def camera(t):
    for (ta, a), (tb, b) in zip(CAMERA, CAMERA[1:]):
        if ta <= t < tb:
            e = ease((t - ta) / (tb - ta))
            return (math.exp(math.log(a[0]) + (math.log(b[0]) - math.log(a[0])) * e), a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e)
    return CAMERA[-1][1] if t >= CAMERA[-1][0] else CAMERA[0][1]


def steady(k):
    """What is random in one thing, the same in every drawing."""
    return np.random.default_rng(7000 + k)


def grown(cx, cy, tip, b):
    """A speech bubble's tail end as the bubble grows from nothing (b: 0..1): it comes out of the bubble with it."""
    return (cx + (tip[0] - cx) * b, cy + (tip[1] - cy) * b)


def page(shift):
    """Draws the next things on a page scrolled up by shift (px)."""
    return framed([1.0, 0.0, 0.0, 0.0, -shift])


def his(cam, shift):
    """Draws the next things on his page, through the camera cam, the page scrolled up by shift."""
    z, qx, qy = cam
    return framed([z, 620.0, 962.0, qx, qy - shift])


def tony(pen, orange, t, glow=0.9, lit=1.0, wide=True, **face):
    """Tony at his table (the first drawing), through the camera in place."""
    blink = any(b <= t < b + 2 / DRAWINGS for b in BLINKS)
    table(pen, wide=wide)
    body(pen)
    head(pen, steady(1), hx=620.0, hy=962.0, tilt=6.0, blink=blink, **face)
    phone_on_table(pen, orange, glow=glow + 0.07 * math.sin(2 * math.pi * t / 1.6), rng=steady(2), lit=lit)


def eyes_on(x, y, at):
    """Where someone at (x, y) looks to see at (both on the page)."""
    dx, dy = at[0] - x, at[1] - y
    d = math.hypot(dx, dy) or 1.0
    return (max(-1.0, min(1.0, 1.3 * dx / d)), max(-1.0, min(1.0, 1.3 * dy / d)))


# --- his page: from the alert in his head to the church far off (scenes 1 to 12)
def his_page(pen, orange, t, shift):
    z, qx, qy = camera(t)
    lx, ly, lids, smile, worry = keyed(FACE, t)
    built = seg(t, said(10, "barrières") - 0.3, said(10, "barrières") + 0.7)  # his wall, row by row

    # « …ou par peur de déranger »: three people talking at their table; « rabaissé »: they loom over him, and judge
    if T[7] <= t < T[10] + 0.9:
        dx = 560 * (1 - ease(seg(t, T[7], T[7] + 0.7)))
        e = ease(seg(t, T[8] - 0.1, T[8] + 0.6))
        gone = 1400 * ease(seg(t, T[10], T[10] + 0.8))
        order = sorted(range(3), key=lambda k: GROUP_PEOPLE[k][0])  # each to its place, without crossing
        nudge = {order[0]: bump(t, said(9, "amis") - 0.05), order[1]: bump(t, said(9, "proches") - 0.05), order[2]: bump(t, said(9, "profs") - 0.05)}
        with page(shift):
            for k, (x, y, s, hair, look, mouth, beard) in enumerate(GROUP_PEOPLE):
                gx, gy = GIANTS[order.index(k)]
                if k == 0 and t >= T[7] + 0.7 and e == 0 and int((t - T[7]) * 4) % 2:
                    mouth = "flat"  # he talks
                sz = lerp(s, 1.0, e) * (1 + 0.07 * nudge.get(k, 0.0))
                px, py = lerp(x + dx, gx, e), lerp(y, gy, e) + 30 * nudge.get(k, 0.0) - gone
                lk = (lerp(look[0], (540 - gx) / 900, e), lerp(look[1], 1.0, e))
                person(pen, px, py, sz, hair, lk, mouth if e < 0.5 else "flat", beard, rng=steady(30 + k), brow=0.8 * e, shade=e > 0.6)
            back_table(pen, lerp(1012, 1080, e) - gone, lerp(560 + dx, -40, e), 1120)
            if e == 0:
                b = pop(seg(t, T[7] + 0.7, T[7] + 1.0)) * (1 - ease(seg(t, T[8] - 0.2, T[8])))
                if b > 0.05:
                    speech(pen, 852 + dx, 560, 108 * b, 66 * b, grown(852 + dx, 560, (846 + dx, 650), b), "talk", rng=steady(40))
            b = pop(seg(t, said(9, "profs") - 0.1, said(9, "profs") + 0.3))  # his school report, the teacher's comment on it
            if b > 0:
                bulletin(pen, 760, lerp(2400, 830, b) - gone, 0.62, comment=seg(t, said(9, "profs") + 0.2, said(9, "profs") + 1.4), rng=steady(90))

    # « Pendant longtemps, j'ai été quelqu'un de renfermé »: seen from far off, he is shut in his own bubble
    clip = None
    if T[4] + 0.6 <= t < T[5]:
        k = 2.4 + (1.0 - 2.4) * ease(seg(t, T[4] + 0.6, T[4] + 1.2))
        if k < 2.3:
            clip = k

    # « J'avais peur du jugement, du regard des autres »: all round him, all looking at him; « Aller vers les gens… »:
    # they go far off, a long way from him; « …dans ma foi »: they are at church
    near = ease(seg(t, T[12], T[12] + 0.9))
    if T[11] <= t < T[14] + 0.2:
        with page(shift):
            p = seg(t, T[13] + 0.1, said(13, "foi") + 0.15)
            if p > 0:  # (drawn first: they stand in its door)
                church(pen, 762, 760, 0.62, p, rng=steady(100))
            at = (560, 1180)  # his head, from the camera on his wall
            for k, (x, y, hair, beard) in enumerate(JUDGES):
                w = (said(11, "jugement"), said(11, "regard"), said(11, "autres"))[k]
                b = pop(seg(t, w - 0.15, w + 0.2))
                if b <= 0.05:
                    continue
                fx, fy = FAR_GROUP[k]
                px, py, sz = lerp(x, fx, near), lerp(y, fy, near), lerp(0.45, 0.12, near) * b
                mouth = "flat" if near < 0.5 else ("talk" if k == 0 and int(t * 4) % 2 else "smile")
                person(pen, px, py, sz, hair, eyes_on(px, py, at) if near < 0.5 else (0.0, 0.2), mouth, beard, rng=steady(50 + k), brow=0.6 * (1 - near))
                back_table(pen, py + 400 * sz, px - 430 * sz, px + 430 * sz, h=300 * sz, vanish=px)
            if near > 0.6:
                dashes(pen, [(330, 1560), (420, 1300), (600, 1180), (660, 980), (740, 800)], seg(t, T[12] + 0.7, said(12, "difficile") + 0.3))

    # Tony at his table, through the camera; his wall in front of him once built
    with his((z, qx, qy), shift):
        tony(pen, orange, t, lit=ease(seg(t, *LIGHT)), look=(lx, ly), lids=lids, smile=smile, worry=worry)
        if built > 0:
            bricks(pen, -420, 1660, 1950, 14, steady(70), p=built, h=44, length=120, orange=orange)

        # « Toi aussi, t'as peur de déranger ? Moi, tout le temps. »: seen close, the alert in his head, « Annuler »
        # circled; « Et pourtant… »: the camera pulls back, it is a thought over him; « Moi c'est Tony »: it goes
        gone = 1 - ease(seg(t, T[3], T[3] + 0.25))
        if gone > 0.05:
            for k, (bx, by, r) in enumerate(TRAIL):
                bubble(pen, bx, by, r * gone, None, rng=steady(10 + k))
            alert(pen, *ALERT, s=gone, circled=seg(t, *CIRCLED), rng=steady(80))

    if clip is not None:
        inside = Image.new("L", pen.img.size, 0)
        ImageDraw.Draw(inside).ellipse([(782 - 252 * clip) * S, (1594 - 274 * clip - shift) * S, (782 + 252 * clip) * S, (1594 + 274 * clip - shift) * S],
                                       fill=255)
        for layer in (pen.img, orange):
            layer.paste(0, (0, 0), ImageOps.invert(inside))
    if T[4] + 0.6 <= t < T[5]:
        with page(shift):
            ring = loop_pts(steady(20), 782, 1594, 262, 282)
            n = int(len(ring) * ease(seg(t, T[4] + 0.6, T[4] + 1.2)))
            if n > 1:
                pen.line(ring[:n], w=3.4, over=0.0, breaks=False, drift=0.8, again=0.0)
            if t >= T[4] + 1.2:
                pen.line(loop_pts(steady(21), 782, 1594, 256, 290), w=1.8, over=0.0, breaks=False, drift=0.8, again=0.0)

    with page(shift):
        # « Le genre de personne qui n'osait pas poser de questions »: a question comes up out of his head, gets stuck
        if q_up <= t < T[6] + 0.2:
            up = pop(seg(t, q_up, q_up + 0.35)) * (1 - ease(seg(t, T[6], T[6] + 0.2)))
            sq_at = said(5, "questions")
            squash = 1 - 0.26 * ease(seg(t, sq_at - 0.1, sq_at + 0.1))
            shake = (2 if int(t * DRAWINGS) % 2 else -2) if t >= sq_at + 0.1 else 0
            if up > 0.05:
                bubble(pen, 656 + shake, 700 - 76 * up, 80 * up, "?", squash=squash, rng=steady(50))
            if sq_at + 0.1 <= t < T[6]:
                for sx in (-1, 1):  # it strains
                    pen.line([(656 + sx * 100, 598), (656 + sx * 112, 612), (656 + sx * 112, 638), (656 + sx * 100, 652)], w=2.2, over=0.0, again=0.0)

        # « Peut-être par peur de dire n'importe quoi… »: what he would say, tangling itself in a speech bubble
        if T[6] + 0.15 <= t < T[7] + 0.2:
            b = pop(seg(t, T[6] + 0.15, T[6] + 0.45)) * (1 - ease(seg(t, T[7], T[7] + 0.2)))
            if b > 0.05:
                speech(pen, 300, 560, 215 * b, 165 * b, grown(300, 560, (436, 900), b), "scribble", p=seg(t, T[6] + 0.4, T[7]), rng=steady(60))

        # « …ou par peur de déranger »: his « … », that he keeps to himself
        if T[7] + 0.75 <= t < T[8] + 0.1:
            b = pop(seg(t, T[7] + 0.75, T[7] + 1.0)) * (1 - ease(seg(t, T[8] - 0.15, T[8] + 0.1)))
            if b > 0.05:
                speech(pen, 562, 878, 62 * b, 44 * b, grown(562, 878, (480, 1000), b), "dots", p=seg(t, T[7] + 0.85, T[7] + 1.3), rng=steady(70))

        # « À force d'entendre ce genre de paroles… »: the words he heard, round him; « …des barrières »: they fall into his wall
        if T[10] + 0.3 <= t < said(10, "barrières") + 0.7:
            for k, (x, y, wd) in enumerate(SCRAWLS):
                p = seg(t, T[10] + 0.3 + 0.3 * k, T[10] + 1.0 + 0.3 * k)
                fall = y + 760 * ease(built)
                if p > 0 and fall < 1440:  # (gone once into the wall, whose top is there)
                    scrawl(pen, x, fall, wd, steady(60 + k), p=p, size=1.7, w=2.8)


# --- « Pourtant, je pense qu'on a tous besoin de frères et sœurs autour de nous… »: a table, and a place free for him
def family_page(pen, orange, t, shift):
    with page(shift):
        for k, (x, hair, mouth, beard) in enumerate(FAMILY):
            if mouth == "talk" and int((t + 0.3 * k) * 4) % 2:
                mouth = "flat"
            person(pen, x, 900, 0.42, hair, (0.6 if x < 540 else -0.6, 0.1), mouth, beard, rng=steady(120 + k))
        chair(pen, 540, 1150, 0.8)
        back_table(pen, 1150, -40, 1120)
        for at, draw in ((said(14, "apprendre"), lambda b: bubble(pen, 250, 560, 85 * b, "book", rng=steady(130))),
                         (said(14, "partager"), lambda b: speech(pen, 540, 470, 110 * b, 70 * b, grown(540, 470, (520, 600), b), "talk", rng=steady(131))),
                         (said(14, "Dieu"), lambda b: bubble(pen, 830, 560, 85 * b, "cross", rng=steady(132)))):
            b = pop(seg(t, at - 0.05, at + 0.25))
            if b > 0.05:
                draw(b)


# --- « C'est justement pour ça que j'ai créé RISE. » and what it is for
def rise_page(pen, orange, t, shift):
    flame = said(15, "RISE")
    e16 = ease(seg(t, T[16] - 0.2, T[16] + 0.5))  # « Pour offrir une communauté… »: up a little, the others round it
    e17 = ease(seg(t, T[17] - 0.2, T[17] + 0.4))  # « Un endroit où… »: big again, for what is on it
    k = lerp(lerp(1.0, 0.6, e16), 0.92, e17) * pop(seg(t, T[15] - 0.15, T[15] + 0.25))
    cy = lerp(lerp(980, 700, e16), 940, e17)
    me = pop(seg(t, said(16, "moi") - 0.1, said(16, "moi") + 0.25))  # « …comme moi »: he is one of them
    down = 900 * e17
    if me > 0.05 and down < 880:
        with his((0.26 * me, 720.0, 1560.0 + down), shift):
            tony(pen, orange, t, wide=False, look=(-0.3, -1.0), lids=13.5, smile=0.2)
    with page(shift):
        for j, (x, y, hair) in enumerate(COMMUNITY):  # those who, like him, don't dare go to others
            b = pop(seg(t, said(16, "communauté") + 0.12 * j, said(16, "communauté") + 0.12 * j + 0.3))
            if b > 0.05 and down < 880:
                if b >= 1:
                    dashes(pen, [(x, y - 150), (lerp(x, 540, 0.5), lerp(y - 150, cy + 300 * k, 0.6)), (540, cy + 300 * k)],
                           seg(t, said(16, "communauté") + 0.4, said(16, "communauté") + 0.9))
                person(pen, x, y + down, 0.3 * b, hair, eyes_on(x, y, (540, cy)), "smile", False, rng=steady(140 + j))
                back_table(pen, y + down + 100 * b, x - 130 * b, x + 130 * b)
        if k <= 0.05:
            return
        x0, y0, x1, y1 = big_phone(pen, 540, cy, k, glow=0.8 * ease(seg(t, flame, flame + 0.4)), rng=steady(140))
        scx, scy = (x0 + x1) / 2, (y0 + y1) / 2
        shows = [(said(17, "témoignages") - 0.1, "talk"), (said(17, "questions") - 0.1, "?"), (said(17, "demander") - 0.1, "alert"),
                 (said(17, "groupes") - 0.1, "groups")]
        now = [(at, what) for at, what in shows if t >= at]
        if not now:
            rise_logo(pen, orange, scx, scy - 40 * k, 400 * k, p=ease(seg(t, flame - 0.05, flame + 0.3)))
            return
        at, what = now[-1]
        b = pop(seg(t, at, at + 0.3))
        if what == "talk":
            speech(pen, scx, scy - 30 * k, 170 * k * b, 110 * k * b, grown(scx, scy - 30 * k, (scx - 60 * k, scy + 150 * k), b), "talk", rng=steady(150))
        elif what == "?":
            bubble(pen, scx, scy, 150 * k * b, "?", rng=steady(151))
        elif what == "alert":  # the alert of the first image: on RISE, he asks
            alert(pen, scx, scy, 0.88 * k * b, circled=seg(t, said(17, "prière"), said(17, "prière") + 0.5), rng=steady(152), pick=1)
        else:
            for j, (dx, hair) in enumerate(((-120, "short"), (0, "long"), (120, "curly"))):
                person(pen, scx + dx * k, scy - 30 * k, 0.17 * k * b, hair, (-dx / 150, 0.1), "smile", False, rng=steady(160 + j))
            back_table(pen, scy + 25 * k, x0 + 10, x1 - 10)


# --- « Parce que je voulais créer l'espace dont j'ai moi-même besoin pour grandir dans ma foi. »: at his table again,
# no wall, his thoughts over him (the first drawing), a smile; then RISE
def last_page(pen, orange, t, shift):
    face = keyed([(T[18], (0.0, 1.0, 12.0, 0.0, 0.0)), (T[18] + 0.5, (0.0, 1.0, 12.0, 0.1, 0.0)), (said(18, "besoin"), (0.0, 1.0, 12.0, 0.1, 0.0)),
                  (said(18, "besoin") + 0.35, (0.12, -0.3, 13.5, 0.35, 0.0))], t)
    lx, ly, lids, smile, worry = face
    with his(BASE, shift):
        tony(pen, orange, t, look=(lx, ly), lids=lids, smile=smile, worry=worry)
    logo = pop(seg(t, T[-1] - 0.1, T[-1] + 0.3))
    with page(shift):
        gone = 1 - ease(seg(t, T[-1] - 0.3, T[-1]))
        for j, ((bx, by, r, sym), at) in enumerate((((456, 724, 12, None), 0.0), ((414, 692, 22, None), 0.1), ((345, 625, 50, None), 0.2),
                                                   ((250, 470, 120, "?"), 0.4), ((420, 330, 95, "chat"), 0.7), ((165, 720, 82, "cross"), 1.0))):
            b = pop(seg(t, said(18, "l'espace") + at, said(18, "l'espace") + at + 0.3)) * gone
            if b > 0.05:
                bubble(pen, bx, by, r * b, sym, rng=steady(10 + j))
        if logo > 0.05:
            rise_logo(pen, orange, 540, 470, 760 * logo, p=ease(seg(t, T[-1] + 0.1, T[-1] + 0.5)))


PAGES = [his_page, family_page, rise_page, last_page]


def spaced_width(ln):
    return letters.width(ln, CAP["font"], CAP["size"]) + CAP["size"] * 0.12 * len(ln)


def chunks(words, most=7):
    """A line cut where he pauses (after « … », a comma, the end of a sentence) or where it would run too long: each
    piece is written on its own, as he says it."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if w["w"].endswith(("…", ".", "?", "!", ",")) and len(cur) >= 3 or len(cur) >= most:
            out.append(cur)
            cur = []
    if cur:
        if out and len(cur) < 3 and len(out[-1]) + len(cur) <= most + 2:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def balanced(text):
    """The text in as few lines as fit, split so that they are as even as can be (no word left alone below)."""
    from itertools import combinations
    words = text.split(" ")
    n = len(letters.wrap(text, CAP["font"], CAP["size"], CAP["width"]))
    best = None
    for cuts in combinations(range(1, len(words)), n - 1):
        lines = [" ".join(words[a:b]) for a, b in zip((0,) + cuts, cuts + (len(words),))]
        widest = max(spaced_width(ln) for ln in lines)
        if best is None or widest < best[0]:
            best = (widest, lines)
    return best[1]


def caption(pen, t):
    """The line he is saying, written by hand at the top, word by word as he says it, a piece at a time."""
    if t < 0.25 or t > T[-1] - 0.1:
        return  # the very first image: the alert alone; and the logo, at the end, alone
    i = max(k for k in range(len(LINES)) if T[k] <= t)
    words = WORDS[i]
    pieces = chunks(words)
    heard = [j for j, w in enumerate(words) if w["start"] <= t + 0.04] or [0]
    piece = next((p for p in pieces if heard[-1] in p), pieces[-1])
    shown = [words[j]["w"].upper() for j in piece if j <= heard[-1]]
    text = " ".join(words[j]["w"].upper() for j in piece)
    n, said_ = 0, len(" ".join(shown).split(" "))
    for li, ln in enumerate(balanced(text)):
        gap = CAP["size"] * 0.12
        x = 540 - spaced_width(ln) / 2
        y = CAP["top"] + li * CAP["line"]
        for word in ln.split(" "):
            if n >= said_:
                return
            strokes, xx = [], x
            for ch in word:  # spaced capitals
                st, _ = letters.layout(ch, CAP["font"], CAP["size"], hand=0.9, seed=zlib.crc32(word.encode()) + len(strokes))
                strokes += [[(xx + a, y + b) for a, b in s] for s in st]
                xx += letters.width(ch, CAP["font"], CAP["size"]) + gap
            for s in strokes:  # a margin of paper round the letters, then the letters
                if len(s) > 1:
                    pen.line(s, w=12, fill=0, amp=0.4, again=0.0, over=0.0, drift=0.0, breaks=False, taper=0.0)
            for s in strokes:
                if len(s) > 1:
                    pen.line(s, w=3.8, amp=0.4, again=0.0, over=0.0, drift=0.0, breaks=False, taper=0.2)
            x = xx + letters.width(" ", CAP["font"], CAP["size"]) + gap
            n += 1


def frame_at(t, v):
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    pen = Hand(img, np.random.default_rng(100 + v))  # the hand: a little different in each drawing
    k = sum(1 for a, _ in SCROLLS if t >= a)  # the page we are on (or leaving, while it scrolls up)
    if k and t < SCROLLS[k - 1][1]:
        a, b = SCROLLS[k - 1]
        up = H * ease(seg(t, a, b))
        PAGES[k - 1](pen, orange, t, up)
        PAGES[k](pen, orange, t, up - H)
    else:
        PAGES[k](pen, orange, t, 0.0)
    caption(pen, t)
    return finish(img, orange, v)


def _render(args):
    g, d = args
    frame_at(g / DRAWINGS, g % 3).save(f"{d}/{g:05d}.png")
    return g


def main(until=END):
    out = ROOT / "renders" / "film_v4.mp4"
    out.parent.mkdir(exist_ok=True)
    n = int(min(until, END) * DRAWINGS)
    with tempfile.TemporaryDirectory() as d:
        with Pool(4) as pool:
            for i, _ in enumerate(pool.imap_unordered(_render, [(g, d) for g in range(n)], chunksize=2)):
                if i % 48 == 0:
                    print(f"{i}/{n}", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(DRAWINGS), "-i", f"{d}/%05d.png", "-i", str(VOICE / "voice.wav"),
                        "-af", "apad", "-ac", "2", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(out, f"{n / DRAWINGS:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--until":
        main(float(sys.argv[2]))
    elif len(sys.argv) > 1:
        for s_ in sys.argv[1:]:
            g = int(float(s_) * DRAWINGS)
            frame_at(g / DRAWINGS, g % 3).save(ROOT / "renders" / f"film_{s_}.png")
    else:
        main()
