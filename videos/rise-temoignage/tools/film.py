"""Tony's film, on his voice (tools/voice.py: assets/voice/voice.wav, and take.json with every word's time), in the
drawing he validated (sketch.py), played the way the reel he sent plays: held drawings redrawn twelve times a second
so the ink boils a little, a few things moving at once, the scenes joined by camera moves rather than cuts (a scroll
to the next page where the place changes). What is random in a drawing (where the hairs, the rays, the tangle are)
stays put from one drawing to the next; only the hand that traces them changes. Every move is keyed to his words,
and so are the key words written into the picture where they belong: no subtitles (« pour que les gens soient plus
concentrés sur la vidéo »).
What matters stays clear of TikTok's own buttons and text (SAFE: the tabs at the top, the column of buttons on the
right, the name and description at the bottom).
It opens on what goes on in his head when he wants to reach out to someone, drawn as his phone's alert (« Demander de
la prière ? Tu risques de déranger. »), « Annuler » circled; near the end the same alert is on RISE, and this time
« Demander » gets circled. It closes on him at his table, smiling a little, then on RISE's signature, the end of
every video: the logo, « Disponible sur les stores » and the App Store and Google Play badges.
Usage: python3 tools/film.py [--court] [--until SECONDS]    -> renders/film_v9.mp4 (--court: film_v9_court.mp4, without
                                                               « Et pourtant… j'ai créé un réseau social. Moi c'est Tony. »)
       python3 tools/film.py [--safe] T1 T2 ...    -> renders/film_T.png (the drawing at those times; --safe: with
                                                     TikTok's buttons and text shaded over it)
"""
import json
import math
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from sketch import (S, H, W, Hand, alert, back_table, barrier, big_phone, body, bricks, bubble, bulletin, chair, church, dashes, finish,
                    framed, handwritten, head, hug, laptop, loop_pts, padlock, person, phone_on_table, rise_logo, scrawl, spline, speech,
                    table)

ROOT = Path(__file__).resolve().parents[1]
FPS, DRAWINGS = 24, 12  # twelve drawings a second, each held two frames
VOICE = ROOT / "assets" / "voice"
# --court: the version without « Et pourtant… j'ai créé un réseau social. Moi c'est Tony. », where viewers left (« les
# gens s'arrêtent quand j'ai dit moi c'est Tony »): from « Moi, tout le temps » straight into his story; its voice
# (voice.py --court) keeps the film's line numbers, the two lines left out without words
SHORT = "--court" in sys.argv
NAME = "_court" if SHORT else ""
TAKE = json.loads((VOICE / f"take{NAME}.json").read_text())
LINES = [line["text"] for line in TAKE["lines"]]
WORDS = [line["words"] for line in TAKE["lines"]]
T = [line["start"] for line in TAKE["lines"]] + [TAKE["duration"]]  # when each line starts; T[-1]: the end of his voice
END = TAKE["duration"] + 3.2  # and RISE's signature, held after his last word
SAFE = [(0, 0, 1080, 200), (930, 640, 1080, 1560), (0, 1480, 1080, 1920)]  # what TikTok covers: tabs, buttons, name and text


def said(i, start):
    """When he says the word of line i that begins with `start`."""
    for w in WORDS[i]:
        if w["w"].lower().lstrip("…").startswith(start.lower()):
            return w["start"]
    raise KeyError((i, start))


# where the camera is on his page: zoom, and where his head lands (it is at 620, 962 in the drawing)
BASE, CORNER, GROUP = (0.9, 620.0, 880.0), (0.42, 300.0, 560.0), (0.92, 300.0, 1100.0)
LOW, WALL, FAR = (0.42, 540.0, 1330.0), (0.75, 560.0, 1000.0), (0.3, 300.0, 1300.0)
ALERT, A_S = (300.0, 520.0), 0.75  # the alert in his head: where it is on his page, and its size there
TRAIL = [(470, 732, 10), (432, 706, 15), (390, 678, 21)]  # little bubbles, from his head up to it
RING = (601.0, 1231.0)  # the bubble he is shut in, round him and his table, on his page
NOTES = [(37, 1395), (142, 1251), (31, 1106), (131, 973)]  # « …un réseau social »: where what comes out of his phone goes
CODE = [("{}", (842, 1196)), ("();", (866, 1066)), ("01", (874, 924))]  # « …j'ai créé… »: what he types, coming off his laptop's screen


def close(z):
    """Close on the alert, at zoom z: it fills the page, a little above the middle and left of TikTok's buttons."""
    return (z, 505.0 + (620.0 - ALERT[0]) * z, 900.0 + (962.0 - ALERT[1]) * z)


CIRCLED = (said(1, "Moi"), said(1, "Moi") + 0.55)  # « Annuler » circled
if SHORT:  # the camera pulls back once « Annuler » is circled; his phone stays off, the alert goes as his story starts
    PULL, LIGHT, GONE = (CIRCLED[1] + 0.05, T[4] - 0.1), (1e9, 1e9 + 0.35), T[4] + 0.3
    TYPING, SHUT, AWAY = 0.0, (0.0, 0.0), (0.0, 0.0)  # (no laptop)
else:
    PULL = (T[2] - 0.1, said(2, "j'ai") + 0.3)  # the camera pulls back: it is a thought over him
    LIGHT = (said(2, "réseau") - 0.05, said(2, "réseau") + 0.3)  # his phone lights up
    GONE = T[3]  # « Moi c'est Tony »: the alert in his head goes
    TYPING = said(2, "créé") - 0.05  # he codes (the camera has come back far enough to see his laptop)
    SHUT = (T[3] - 0.62, T[3] - 0.38)  # once it is said, his laptop shuts…
    AWAY = (T[3] - 0.38, T[3] - 0.12)  # …and goes: his table bare again for « Moi c'est Tony »
CAMERA = [(0.0, close(2.3)), (PULL[0], close(2.42)), (PULL[1], BASE),
          (T[4], BASE), (T[4] + 0.8, CORNER), (T[5], CORNER), (T[5] + 0.55, BASE),  # « renfermé »: far off, in a corner
          (T[7], BASE), (T[7] + 0.7, GROUP),  # « …ou par peur de déranger »: the others, at their table
          (T[8] - 0.1, GROUP), (T[8] + 0.6, LOW),  # « rabaissé »: small, under them
          (T[10], LOW), (T[10] + 0.8, WALL),  # « …des barrières »: his wall
          (T[12], WALL), (T[12] + 0.9, FAR)]  # « Aller vers les gens… »: far from them
PROFS, CARD = said(9, "profs"), said(9, "même")  # « …même par des profs »: his report card comes
q_up = said(5, "n'osait")
# his face: where he looks (across, down), how open his lids are, his smile, his worry
FACE = [(0.0, (0.0, 1.0, 12.0, 0.0, 0.0))] + ([] if SHORT else [  # « Moi c'est Tony »: up at us, a little smile
            (T[3] + 0.05, (0.0, 1.0, 12.0, 0.0, 0.0)), (T[3] + 0.3, (0.12, -0.3, 13.5, 0.0, 0.0)),
            (T[3] + 0.45, (0.12, -0.3, 13.5, 0.0, 0.0)), (T[3] + 0.75, (0.12, -0.3, 13.5, 0.3, 0.0)), (T[4], (0.12, -0.3, 13.5, 0.3, 0.0))]) + [
        (T[4] + 0.25, (0.0, 1.0, 12.0, 0.0, 0.1)), (T[4] + 0.7, (0.0, 1.0, 12.0, 0.0, 0.35)), (q_up, (0.0, 1.0, 12.0, 0.0, 0.35)),
        (q_up + 0.3, (0.15, -1.1, 13.0, -0.25, 0.45)), (T[6] + 0.1, (0.15, -1.1, 13.0, -0.25, 0.45)),
        (T[6] + 0.35, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[7] + 0.3, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[7] + 0.6, (0.95, -0.6, 13.0, -0.15, 0.4)),
        (T[8], (0.95, -0.6, 13.0, -0.15, 0.4)), (T[8] + 0.4, (0.0, -1.2, 13.5, -0.3, 0.7)),  # up at them
        (said(9, "amis") - 0.1, (0.0, -1.2, 13.5, -0.3, 0.7)), (said(9, "amis") + 0.15, (-0.8, -1.0, 13.5, -0.3, 0.7)),
        (said(9, "proches") - 0.1, (-0.8, -1.0, 13.5, -0.3, 0.7)), (said(9, "proches") + 0.15, (0.0, -1.2, 13.5, -0.3, 0.75)),
        (CARD - 0.1, (0.0, -1.2, 13.5, -0.3, 0.75)), (CARD + 0.15, (0.8, -1.0, 13.5, -0.35, 0.8)),
        (CARD + 0.5, (0.8, -1.0, 13.5, -0.35, 0.8)), (CARD + 0.8, (0.0, -1.2, 12.5, -0.4, 0.8)),  # up at his report
        (T[10] + 0.2, (0.0, -1.2, 12.5, -0.4, 0.8)), (T[10] + 0.7, (0.0, 0.8, 12.0, -0.2, 0.5)),  # down, behind his wall
        (said(11, "jugement") - 0.1, (0.0, 0.8, 12.0, -0.2, 0.5)), (said(11, "jugement") + 0.1, (-0.9, -0.7, 13.5, -0.3, 0.7)),
        (said(11, "regard") - 0.1, (-0.9, -0.7, 13.5, -0.3, 0.7)), (said(11, "regard") + 0.1, (0.9, -0.3, 13.5, -0.35, 0.8)),
        (said(11, "autres") - 0.1, (0.9, -0.3, 13.5, -0.35, 0.8)), (said(11, "autres") + 0.1, (-0.9, -0.2, 13.5, -0.35, 0.8)),
        (T[12] + 0.5, (-0.9, -0.2, 13.5, -0.35, 0.8)), (T[12] + 1.0, (0.7, -0.9, 12.5, -0.2, 0.5))]  # over to them, far off
BLINKS = [LIGHT[1] + 0.15, T[5] - 0.25, T[9] + 0.3, T[11] - 0.2, T[13] + 0.7, T[18] + 0.6, T[18] + 2.4]
GROUP_PEOPLE = [(700, 730, 0.46, "short", (-0.6, 0.2), "talk", True), (560, 760, 0.46, "long", (0.8, 0.1), "smile", False),
                (840, 775, 0.46, "curly", (-0.9, 0.1), "smile", False)]
GIANTS = [(215, 560), (540, 520), (850, 560)]  # where they loom over him (the same three, left to right as they sat)
JUDGES = [(180, 400, "short", True), (820, 760, "long", False), (200, 800, "curly", False)]  # « …du regard des autres »
LAUGHS = [(190, 250), (660, 700), (370, 720)]  # their « HA HA »
FAR_GROUP = [(690, 770), (762, 764), (834, 770)]  # the same three, far off: at the church
PATH = [(340, 1220), (420, 1130), (540, 1070), (640, 980), (740, 860)]  # from him to them
SCRAWLS = [(80, 460, 260), (720, 520, 280), (160, 720, 220), (760, 760, 240)]  # the words he heard, round him
FAMILY = [(190, "short", "talk", False), (375, "long", "smile", False), (705, "curly", "smile", False), (860, "short", "talk", True)]
COMMUNITY = [(180, 1150, "long"), (860, 1150, "short"), (330, 1330, "curly")]
ME = (650.0, 1300.0)  # him among them (where his head is: clear of the table of the one behind, on his right)
SCROLLS = [(T[14] - 0.35, T[14] + 0.1), (T[15] - 0.55, T[15] - 0.1), (T[18] - 0.5, T[18] - 0.05), (T[-1] + 0.2, T[-1] + 0.65)]  # to the next page
SIGN = SCROLLS[3][0]  # RISE's signature, at the end of every video: its logo, « Disponible sur les stores », the badges
BADGES = [Image.open(ROOT / "assets" / "brand" / f).convert("RGBA") for f in ("badge_app_store_fr.png", "badge_google_play_fr.png")]


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


LEAD = 1.0  # key words come this long before he says them, and are quickly written: time to read them


def key(pen, text, x, y, at, t, size=44.0, gone=None, after=None):
    """A key word of what he says, written by hand where it belongs in the picture, LEAD before he says it (at),
    not before after (its scene)."""
    start = at - LEAD if after is None else max(after, at - LEAD)
    if t >= start and (gone is None or t < gone):
        handwritten(pen, text, x, y, size, seg(t, start, start + 0.2 + 0.015 * len(text)), w=max(4.4, 0.07 * size))


def tony(pen, orange, t, glow=0.9, lit=1.0, wide=True, **face):
    """Tony at his table (the first drawing), through the camera in place; RISE on his phone."""
    blink = any(b <= t < b + 2 / DRAWINGS for b in BLINKS)
    table(pen, wide=wide)
    body(pen)
    head(pen, steady(1), hx=620.0, hy=962.0, tilt=6.0, blink=blink, **face)
    phone_on_table(pen, orange, glow=glow + 0.07 * math.sin(2 * math.pi * t / 1.6), rng=steady(2), lit=lit, logo=True)


def eyes_on(x, y, at):
    """Where someone at (x, y) looks to see at (both on the page)."""
    dx, dy = at[0] - x, at[1] - y
    d = math.hypot(dx, dy) or 1.0
    return (max(-1.0, min(1.0, 1.3 * dx / d)), max(-1.0, min(1.0, 1.3 * dy / d)))


def along(pts, f):
    """The point at f (0..1) of the way along a smooth curve through pts."""
    path = np.array(spline(pts, 10), float)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(path, axis=0).T))]
    i = min(len(path) - 1, int(np.searchsorted(d, f * d[-1])))
    return tuple(path[i])


# --- his page: from the alert in his head to the church far off
def his_page(pen, orange, red, t, shift):
    z, qx, qy = camera(t)
    lx, ly, lids, smile, worry = keyed(FACE, t)
    built = seg(t, said(10, "barrières") - 1.2, said(10, "barrières") - 0.2)  # his wall, row by row

    # « …ou par peur de déranger »: three people talking at their table; « rabaissé »: they loom over him, and judge
    if T[7] <= t < T[10] + 0.9:
        dx = 560 * (1 - ease(seg(t, T[7], T[7] + 0.7)))
        e = ease(seg(t, T[8] - 0.1, T[8] + 0.6))
        gone = 1400 * ease(seg(t, T[10], T[10] + 0.8))
        order = sorted(range(3), key=lambda k: GROUP_PEOPLE[k][0])  # each to its place, without crossing
        names = [(said(9, "amis"), "AMIS"), (said(9, "proches"), "PROCHES"), (PROFS, "PROFS")]
        with page(shift):
            for k, (x, y, s, hair, look, mouth, beard) in enumerate(GROUP_PEOPLE):
                j = order.index(k)
                gx, gy = GIANTS[j]
                if k == 0 and t >= T[7] + 0.7 and e == 0 and int((t - T[7]) * 4) % 2:
                    mouth = "flat"  # he talks
                nudge = bump(t, names[j][0] - 0.05)
                sz = lerp(s, 0.8, e) * (1 + 0.07 * nudge)
                px, py = lerp(x + dx, gx, e), lerp(y, gy, e) + 30 * nudge - gone
                lk = (lerp(look[0], (540 - gx) / 900, e), lerp(look[1], 1.0, e))
                person(pen, px, py, sz, hair, lk, mouth if e < 0.5 else "flat", beard, rng=steady(30 + k), brow=0.8 * e, shade=e > 0.6)
            back_table(pen, lerp(960, 1080, e) - gone, lerp(460 + dx, -40, e), 1120, h=lerp(150, 100, e))
            for j, (at, name) in enumerate(names):  # their names on the bench, as he says them
                key(pen, name, GIANTS[j][0], 1150 - gone, at, t, 40, after=T[9] - 0.4)
            key(pen, "RABAISSÉ", 820, 1420 - gone, said(8, "rabaissé"), t, 46, after=T[8] + 0.3)
            if e == 0:  # what he fears they would say to him
                b = pop(seg(t, T[7] + 0.35, T[7] + 0.65)) * (1 - ease(seg(t, T[8] - 0.25, T[8] - 0.1)))
                if b > 0.05:
                    speech(pen, 620 + dx, 470, 290 * b, 85 * b, grown(620 + dx, 470, (680 + dx, 620), b), "text", p=seg(t, T[7] + 0.55, T[7] + 1.3),
                           rng=steady(40), text="Laisse-nous tranquille !")
                key(pen, "DÉRANGER", 540, 330, said(7, "déranger"), t, 46, gone=T[8] - 0.1, after=T[7])
            b = pop(seg(t, CARD - 0.1, CARD + 0.3))  # his school report, then big, the teacher's comment written on it in red
            if b > 0:
                g = ease(seg(t, CARD + 0.4, CARD + 0.9))
                bulletin(pen, lerp(760, 540, g), lerp(lerp(2400, 830, b), 780, g) - gone, lerp(0.55, 1.1, g), tilt=lerp(-5, -3, g),
                         comment=seg(t, CARD + 0.5, CARD + 1.3), rng=steady(90), red=red)

    # « J'avais peur du jugement… »: someone mocks him; « …du regard des autres »: they all laugh at him;
    # « Aller vers les gens était devenu difficile »: far off, a long way from him, and the way is locked;
    # « Et aujourd'hui encore, ça me freine dans ma foi »: they are at church, and barriers stand all along the way
    near = ease(seg(t, T[12], T[12] + 0.9))
    if T[11] <= t < T[14] + 0.2:
        J, R, A = said(11, "jugement"), said(11, "regard"), said(11, "autres")
        with page(shift):
            p = seg(t, T[13] + 0.1, said(13, "foi") + 0.15)
            if p > 0:  # (drawn first: they stand in its door)
                church(pen, 762, 830, 0.62, p, rng=steady(100))
            at = (560, 1000)  # his head, from the camera on his wall
            for k, (x, y, hair, beard) in enumerate(JUDGES):
                b = pop(seg(t, (J, R, A)[k] - 0.15, (J, R, A)[k] + 0.2))
                if b <= 0.05:
                    continue
                fx, fy = FAR_GROUP[k]
                px, py, sz = lerp(x, fx, near), lerp(y, fy, near), lerp(0.45, 0.12, near) * b
                if near >= 0.5:
                    mouth = "talk" if k == 0 and int(t * 4) % 2 else "smile"
                elif t >= R:
                    mouth = "laugh"
                else:
                    mouth = "talk" if k == 0 and int(t * 5) % 2 else "flat"
                person(pen, px, py, sz, hair, eyes_on(px, py, at) if near < 0.5 else (0.0, 0.2), mouth, beard, rng=steady(50 + k),
                       brow=0.6 * (1 - near))
                back_table(pen, py + 400 * sz, px - 430 * sz, px + 430 * sz, h=300 * sz, vanish=px)
            if T[11] <= t < T[12] + 0.15:
                out = 1 - ease(seg(t, T[12], T[12] + 0.15))
                b = pop(seg(t, J - 0.05, J + 0.25)) * out
                if b > 0.05:  # what they say: a mockery, written as it is said
                    speech(pen, 590, 430, 230 * b, 95 * b, grown(590, 430, (330, 470), b), "text", p=seg(t, J + 0.2, J + 1.1), rng=steady(55),
                           text="Haha, n'importe quoi…")
                if t >= R:
                    for k, (hx_, hy_) in enumerate(LAUGHS):
                        if t >= (J, R, A)[k] and out > 0.5:
                            handwritten(pen, "HA HA", hx_ + (3 if int(t * 8) % 2 else -3), hy_, 30, seg(t, max(R, (J, R, A)[k]), max(R, (J, R, A)[k]) + 0.3))
                if out > 0.5:
                    key(pen, "JUGEMENT", 590, 290, J, t, 44, after=T[11])
                    key(pen, "REGARD DES AUTRES", 590, 600, R, t, 40, after=T[11] + 0.4)
            if near > 0.6:
                dashes(pen, PATH, seg(t, T[12] + 0.7, said(12, "difficile") + 0.3))
                D = said(12, "difficile")
                b = pop(seg(t, D - 0.1, D + 0.25))
                if b > 0.05:  # the way to them: locked
                    shake = 3 * math.sin(40 * (t - D)) if D + 0.45 <= t < D + 0.8 else 0.0
                    lx_, ly_ = along(PATH, 0.5)
                    padlock(pen, lx_ + shake, ly_ - 30, 0.55 * b, shut=ease(seg(t, D + 0.2, D + 0.45)))
                key(pen, "DIFFICILE", 770, 1160, D, t, 44, after=T[12] + 0.6)
                F, Fo = said(13, "freine"), said(13, "foi")
                for k, f in enumerate((0.2, 0.36, 0.66, 0.82)):  # barriers, one after the other, all along it
                    b = pop(seg(t, F + k * (Fo - F) / 4, F + k * (Fo - F) / 4 + 0.25))
                    if b > 0.05:
                        bx, by = along(PATH, f)
                        barrier(pen, bx, by + 20, 0.42 * b, tilt=-8 + 6 * k)
                key(pen, "AUJOURD'HUI ENCORE", 540, 300, said(13, "aujourd'hui"), t, 44, after=T[13] - 0.3)
                key(pen, "MA FOI", 760, 375, Fo, t, 44, after=T[13] + 0.3)

    # « À force d'entendre ce genre de paroles… »: the words he heard, round him; « …des barrières »: they fall into his wall
    if T[10] + 0.3 <= t < said(10, "barrières") - 0.2:
        with page(shift):
            for k, (x, y, wd) in enumerate(SCRAWLS):
                p = seg(t, T[10] + 0.3 + 0.3 * k, T[10] + 1.0 + 0.3 * k)
                fall = y + 760 * ease(built)
                if p > 0 and fall < 1260:  # (gone once into the wall, whose top is there)
                    scrawl(pen, x, fall, wd, steady(60 + k), p=p, size=1.7, w=2.8)

    # Tony at his table, through the camera; his wall in front of him once built; what is in his head, round him
    with his((z, qx, qy), shift):
        tony(pen, orange, t, lit=ease(seg(t, *LIGHT)), look=(lx, ly), lids=lids, smile=smile, worry=worry)
        if t < AWAY[1]:  # « Et pourtant… j'ai créé un réseau social »: at his table, coding on his laptop (« je code »)
            laptop(pen, 668, 1560, 1 - ease(seg(t, *AWAY)), shut=seg(t, *SHUT))
            for j, (sym, (cx_, cy_)) in enumerate(CODE):
                b = pop(seg(t, TYPING + 0.22 * j, TYPING + 0.22 * j + 0.3)) * (1 - ease(seg(t, SHUT[0] - 0.12, SHUT[0] + 0.08)))
                if b > 0.05:
                    handwritten(pen, sym, cx_, cy_, 54 * b, w=5.4)
        if not SHORT and t < T[3] + 0.2:
            key(pen, "RÉSEAU SOCIAL", 620 + (650 - 620) / 0.9, 962 + (300 - 880) / 0.9, said(2, "réseau"), t, 46 / 0.9, after=T[2] + 0.3)
        if not SHORT and t < T[4] + 0.5:  # « Moi c'est Tony »: his name beside him (no arrow: « ça fait enfantin »)
            key(pen, "TONY", 214, 895, said(3, "Tony"), t, 80, after=T[3] - 0.6)
        if built > 0:
            bricks(pen, -420, 1660, 1950, 14, steady(70), p=built, h=44, length=120, orange=orange)
            if t < T[12] + 0.3:
                key(pen, "BARRIÈRES", 620, 1500, said(10, "barrières"), t, 62, after=said(10, "barrières") - 0.9)

        # « …j'ai créé un réseau social »: what it is made of comes out of his phone, one thing after another
        if LIGHT[0] <= t < T[3] - 0.4:
            out = 1 - ease(seg(t, T[3] - 0.65, T[3] - 0.4))
            for j, ((bx, by), sym) in enumerate(zip(NOTES, ("heart", "chat", "?", "cross"))):
                f = ease(seg(t, LIGHT[0] + 0.15 * j, LIGHT[0] + 0.15 * j + 0.35))
                if f > 0.05 and out > 0.05:
                    bubble(pen, lerp(295, bx, f), lerp(1575, by, f), 46 * pop(f) * out, sym, rng=steady(170 + j))

        # « Toi aussi, t'as peur de déranger ? Moi, tout le temps. »: seen close, the alert in his head, « Annuler »
        # circled; « Et pourtant… »: the camera pulls back, it is a thought over him; « Moi c'est Tony »: it goes
        gone = 1 - ease(seg(t, GONE, GONE + 0.25))
        if gone > 0.05:
            for k, (bx, by, r) in enumerate(TRAIL):
                bubble(pen, bx, by, r * gone, None, rng=steady(10 + k))
            alert(pen, *ALERT, s=A_S * gone, circled=seg(t, *CIRCLED), rng=steady(80))

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
                key(pen, "N'IMPORTE QUOI", 300, 345, said(6, "n'importe"), t, 50, after=T[6] + 0.2)  # (over his bubble)

        # « …ou par peur de déranger »: his « … », that he keeps to himself
        if T[7] + 0.75 <= t < T[8] + 0.1:
            b = pop(seg(t, T[7] + 0.75, T[7] + 1.0)) * (1 - ease(seg(t, T[8] - 0.15, T[8] + 0.1)))
            if b > 0.05:
                speech(pen, 750, 690, 67 * b, 48 * b, grown(750, 690, (674, 842), b), "dots", p=seg(t, T[7] + 0.85, T[7] + 1.3), rng=steady(70))

    # « Pendant longtemps, j'ai été quelqu'un de renfermé »: seen from far off, he is shut in his own bubble
    if T[4] + 0.6 <= t < T[5]:
        k = 2.4 + (1.0 - 2.4) * ease(seg(t, T[4] + 0.6, T[4] + 1.2))
        cx, cy = qx + (RING[0] - 620) * z, qy + (RING[1] - 962) * z - shift
        if k < 2.3:
            inside = Image.new("L", pen.img.size, 0)
            ImageDraw.Draw(inside).ellipse([(cx - 600 * z * k) * S, (cy - 652 * z * k) * S, (cx + 600 * z * k) * S, (cy + 652 * z * k) * S], fill=255)
            for layer in (pen.img, orange):
                layer.paste(0, (0, 0), ImageOps.invert(inside))
        with his((z, qx, qy), shift):
            ring = loop_pts(steady(20), RING[0], RING[1], 624, 671)
            n = int(len(ring) * ease(seg(t, T[4] + 0.6, T[4] + 1.2)))
            if n > 1:
                pen.line(ring[:n], w=3.4, over=0.0, breaks=False, drift=0.8, again=0.0)
            if t >= T[4] + 1.2:
                pen.line(loop_pts(steady(21), RING[0], RING[1], 610, 690), w=1.8, over=0.0, breaks=False, drift=0.8, again=0.0)
        with page(shift):
            key(pen, "RENFERMÉ", 720, 1040, said(4, "renfermé"), t, 56, after=T[4] + 0.6)


# --- « Pourtant, je pense qu'on a tous besoin de frères et sœurs autour de nous… »: a table, and a place free for him
def family_page(pen, orange, red, t, shift):
    nous = said(14, "nous")
    with page(shift):
        for k, (x, hair, mouth, beard) in enumerate(FAMILY):
            if mouth == "talk" and int((t + 0.3 * k) * 4) % 2:
                mouth = "flat"
            look = eyes_on(x, 900, (540, 1060)) if t >= nous else (0.6 if x < 540 else -0.6, 0.1)  # « …autour de nous »: the free place
            person(pen, x, 900, 0.42, hair, look, mouth, beard, rng=steady(120 + k))
        chair(pen, 540, 1150, 0.8)
        back_table(pen, 1150, -40, 1120)
        key(pen, "FRÈRES ET SŒURS", 540, 330, said(14, "frères"), t, 46, after=T[14] + 0.2)
        for at, word, x, draw in ((said(14, "apprendre"), "APPRENDRE", 200, lambda b: bubble(pen, 200, 560, 85 * b, "book", rng=steady(130))),
                                  (said(14, "partager"), "PARTAGER", 520,
                                   lambda b: speech(pen, 520, 480, 110 * b, 70 * b, grown(520, 480, (500, 600), b), "talk", rng=steady(131))),
                                  (said(14, "Dieu"), "AVEC DIEU", 810, lambda b: bubble(pen, 810, 560, 85 * b, "cross", rng=steady(132)))):
            b = pop(seg(t, at - 0.85, at - 0.55))  # (before he says it: time to see it)
            if b > 0.05:
                draw(b)
                key(pen, word, x, 700, at, t, 26, after=at - 0.85)


# --- « C'est justement pour ça que j'ai créé RISE. » and what it is for
def rise_page(pen, orange, red, t, shift):
    flame = said(15, "RISE")
    G = said(17, "groupes")
    e16 = ease(seg(t, T[16] - 0.2, T[16] + 0.5))  # « Pour offrir une communauté… »: up a little, the others round it
    e17 = ease(seg(t, T[17] - 0.2, T[17] + 0.4))  # « Un endroit où… »: big again, for what is on it
    into = ease(seg(t, G - 0.3, G + 0.1))  # « …rejoindre des groupes »: into it
    k = lerp(lerp(lerp(1.0, 0.58, e16), 0.9, e17), 2.3, into) * pop(seg(t, T[15] - 0.15, T[15] + 0.25))
    cy = lerp(lerp(lerp(950, 640, e16), 900, e17), 104, into)  # (into it: up, so that the people in it are in the middle)
    down = 900 * e17
    me = pop(seg(t, said(16, "moi") - 0.1, said(16, "moi") + 0.25))  # « …comme moi »: he is one of them
    shy, toward = said(16, "n'osent"), said(16, "autres")
    if me > 0.05 and down < 880:
        with his((0.26 * me, ME[0], ME[1] + down), shift):
            tony(pen, orange, t, wide=False, look=(-0.3, -1.0), lids=13.5, smile=0.2)
    with page(shift):
        for j, (x, y, hair) in enumerate(COMMUNITY):  # those who, like him, don't dare go to others
            b = pop(seg(t, said(16, "communauté") + 0.12 * j, said(16, "communauté") + 0.12 * j + 0.3))
            if b > 0.05 and down < 880:
                if b >= 1 and t >= toward:  # « …aller vers les autres »: through it, they do
                    dashes(pen, [(x, y - 150), (lerp(x, 540, 0.5), lerp(y - 150, cy + 290 * k, 0.6)), (540, cy + 290 * k)], seg(t, toward, toward + 0.5))
                person(pen, x, y + down, 0.3 * b, hair, eyes_on(x, y, (540, cy)), "smile", False, rng=steady(140 + j))
                back_table(pen, y + down + 100 * b, x - 130 * b, x + 130 * b, h=90 * b, vanish=x)
                h = pop(seg(t, shy + 0.1 * j, shy + 0.1 * j + 0.25)) * (1 - ease(seg(t, toward, toward + 0.2)))
                if h > 0.05:  # « …n'osent pas »: each their « … »
                    speech(pen, x + 70, y - 120 + down, 46 * h, 32 * h, grown(x + 70, y - 120 + down, (x + 30, y - 70 + down), h), "dots", rng=steady(145 + j))
        key(pen, "UNE COMMUNAUTÉ", 540, 1010, said(16, "communauté"), t, 46, gone=T[17] - 0.2, after=T[16] + 0.3)
        if k <= 0.05:
            return
        x0, y0, x1, y1 = big_phone(pen, 540, cy, k, glow=0.8 * ease(seg(t, flame, flame + 0.4)), rng=steady(140))
        scx, scy = (x0 + x1) / 2, (y0 + y1) / 2
        shows = [(said(17, "témoignages") - 0.7, "talk", "TÉMOIGNAGES"), (said(17, "questions") - 0.7, "?", "QUESTIONS"),
                 (said(17, "demander") - 0.7, "alert", "PRIÈRE"), (G - 0.7, "groups", "GROUPES")]  # (each before he says it)
        now = [s_ for s_ in shows if t >= s_[0]]
        if not now:
            rise_logo(pen, orange, scx, scy - 40 * k, 400 * k, p=ease(seg(t, flame - 0.05, flame + 0.3)))
            return
        at, what, word = now[-1]
        b = pop(seg(t, at, at + 0.3))
        if what == "talk":
            speech(pen, scx, scy - 30 * k, 170 * k * b, 110 * k * b, grown(scx, scy - 30 * k, (scx - 60 * k, scy + 150 * k), b), "talk", rng=steady(150))
        elif what == "?":
            bubble(pen, scx, scy, 150 * k * b, "?", rng=steady(151))
        elif what == "alert":  # the alert of the first image: on RISE, he asks
            alert(pen, scx, scy, 0.88 * k * b, circled=seg(t, said(17, "prière"), said(17, "prière") + 0.5), rng=steady(152), pick=1)
        else:  # « …rejoindre des groupes »: people holding each other close
            hug(pen, scx, y1 - 12 * k * b, 0.3 * k * b, rng=steady(160))  # (their busts cut at its bottom edge)
            pen.line([(x0 + 6, y1), (x1 - 6, y1)], w=2.2, over=0.0, again=0.0)
        handwritten(pen, word, 540, 380, 46, seg(t, at, at + 0.35))


# --- « Parce que je voulais créer l'espace dont j'ai moi-même besoin pour grandir dans ma foi. »: at his table again,
# no wall, his thoughts over him (the first drawing), a smile; « grandir »: his faith grows
def last_page(pen, orange, red, t, shift):
    face = keyed([(T[18], (0.0, 1.0, 12.0, 0.0, 0.0)), (T[18] + 0.5, (0.0, 1.0, 12.0, 0.1, 0.0)), (said(18, "besoin"), (0.0, 1.0, 12.0, 0.1, 0.0)),
                  (said(18, "besoin") + 0.35, (0.12, -0.3, 13.5, 0.35, 0.0))], t)
    lx, ly, lids, smile, worry = face
    grow = pop(seg(t, said(18, "grandir") - 0.05, said(18, "grandir") + 0.4))
    with his(BASE, shift):
        tony(pen, orange, t, look=(lx, ly), lids=lids, smile=smile, worry=worry)
        for j, ((bx, by, r, sym), at) in enumerate((((456, 724, 12, None), 0.0), ((414, 692, 22, None), 0.1), ((345, 625, 50, None), 0.2),
                                                   ((250, 470, 120, "?"), 0.4), ((420, 330, 95, "chat"), 0.7), ((165, 720, 82, "cross"), 1.0))):
            b = pop(seg(t, said(18, "l'espace") + at, said(18, "l'espace") + at + 0.3))
            if b > 0.05:
                bubble(pen, bx, by, r * b * (1 + 0.45 * grow if sym == "cross" else 1), sym, rng=steady(10 + j))
    with page(shift):
        key(pen, "GRANDIR DANS MA FOI", 540, 300, said(18, "grandir"), t, 44, after=T[18] + 0.5)


# --- RISE's signature, the end of every video: the logo, its flame lighting up, « Disponible sur les stores » and the
# App Store and Google Play badges (the stores' own, pasted in by frame_at: never redrawn)
def signature_page(pen, orange, red, t, shift):
    logo = pop(seg(t, SIGN + 0.35, SIGN + 0.75))
    with page(shift):
        if logo > 0.05:
            rise_logo(pen, orange, 540, 720, 760 * logo, p=ease(seg(t, SIGN + 0.6, SIGN + 1.0)))
        if t >= SIGN + 0.9:
            handwritten(pen, "DISPONIBLE SUR LES STORES", 540, 1040, 33, seg(t, SIGN + 0.9, SIGN + 1.3))


def badges(im, t):
    """The two stores' badges, side by side under « Disponible sur les stores », each popping in."""
    for j, badge in enumerate(BADGES):
        b = pop(seg(t, SIGN + 1.1 + 0.12 * j, SIGN + 1.4 + 0.12 * j))
        if b > 0.05:
            w, h = int(360 * b), int(120 * b)
            cx, cy = (348, 1140) if j == 0 else (732, 1140)
            small = badge.resize((w, h), Image.LANCZOS)
            im.paste(small, (int(cx - w / 2), int(cy - h / 2)), small)
    return im


PAGES = [his_page, family_page, rise_page, last_page, signature_page]


def frame_at(t, v):
    img = Image.new("L", (W * S, H * S), 0)
    orange = Image.new("L", (W * S, H * S), 0)
    red_ink = Image.new("L", (W * S, H * S), 0)
    pen = Hand(img, np.random.default_rng(100 + v))  # the hand: a little different in each drawing
    red = Hand(red_ink, np.random.default_rng(300 + v))  # the teacher's pen
    k = sum(1 for a, _ in SCROLLS if t >= a)  # the page we are on (or leaving, while it scrolls up)
    if k and t < SCROLLS[k - 1][1]:
        a, b = SCROLLS[k - 1]
        up = H * ease(seg(t, a, b))
        PAGES[k - 1](pen, orange, red, t, up)
        PAGES[k](pen, orange, red, t, up - H)
    else:
        PAGES[k](pen, orange, red, t, 0.0)
    im = finish(img, orange, v, red_ink)
    return badges(im, t) if t >= SIGN + 1.1 else im


def shaded(im):
    """The drawing with what TikTok puts over it shaded, to see what it hides."""
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for box in SAFE:
        d.rectangle(box, fill=(255, 0, 60, 70))
    return Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")


def _render(args):
    g, d = args
    frame_at(g / DRAWINGS, g % 3).save(f"{d}/{g:05d}.png")
    return g


def main(until=END):
    out = ROOT / "renders" / f"film_v9{NAME}.mp4"
    out.parent.mkdir(exist_ok=True)
    n = int(min(until, END) * DRAWINGS)
    with tempfile.TemporaryDirectory() as d:
        with Pool(4) as pool:
            for i, _ in enumerate(pool.imap_unordered(_render, [(g, d) for g in range(n)], chunksize=2)):
                if i % 48 == 0:
                    print(f"{i}/{n}", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(DRAWINGS), "-i", f"{d}/%05d.png", "-i", str(VOICE / f"voice{NAME}.wav"),
                        "-af", "apad", "-ac", "2", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(out, f"{n / DRAWINGS:.1f}s")


if __name__ == "__main__":
    args = sys.argv[1:]
    safe = "--safe" in args
    args = [a for a in args if a not in ("--safe", "--court")]
    if len(args) > 1 and args[0] == "--until":
        main(float(args[1]))
    elif args:
        for s_ in args:
            g = int(float(s_) * DRAWINGS)
            im = frame_at(g / DRAWINGS, g % 3)
            (shaded(im) if safe else im).save(ROOT / "renders" / f"film{NAME}_{s_}.png")
    else:
        main()
