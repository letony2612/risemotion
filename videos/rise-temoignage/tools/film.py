"""Tony's film, animated, in the drawing he validated (sketch.py): one drawing per line of SCRIPT.md, played the
way the reel he sent plays: held drawings redrawn twelve times a second so the ink boils a little, a few things
moving at once, the scenes joined by camera moves rather than cuts. What is random in a drawing (where the hairs,
the rays, the tangle are) stays put from one drawing to the next; only the hand that traces them changes.
It opens on what goes on in his head when he wants to reach out to someone, drawn as his phone's alert (« Demander de
la prière ? Tu risques de déranger. »): « Annuler » gets circled, the camera pulls back and it is a thought over his
head; his phone, dark till then, lights up as he says he created a social network.
His voice is not recorded yet: each line is written at the top, word by word, at a speaking pace; everything is
retimed to his voice once he has recorded it.
Usage: python3 tools/film.py [--until SECONDS]  -> renders/film_v3.mp4
       python3 tools/film.py T1 T2 ...         -> renders/film_T.png (the drawing at those times)
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

import letters
from sketch import (S, H, W, Hand, alert, back_table, body, bubble, finish, framed, head, loop_pts, person, phone_on_table,
                    speech, table)

ROOT = Path(__file__).resolve().parents[1]
FPS, DRAWINGS = 24, 12  # twelve drawings a second, each held two frames
WPS = 2.9  # words a second, as he would say them
PAUSE = 0.3  # and how long he stops where a line is cut (after « … » or the end of a sentence)
LINES = [  # each line of SCRIPT.md and how long it is given
    ("Toi aussi, t'as peur de déranger ? Moi, tout le temps. Et pourtant… j'ai créé un réseau social.", 7.6),
    ("Moi c'est Tony.", 2.0),
    ("Pendant longtemps, j'ai été quelqu'un de renfermé.", 3.0),
    ("Le genre de personne qui n'osait pas poser de questions.", 3.9),
    ("Peut-être par peur de dire n'importe quoi…", 3.0),
    ("…ou par peur de déranger.", 3.0),
]
T = np.concatenate([[0.0], np.cumsum([d for _, d in LINES])])  # when each line starts; T[-1]: the end
END = float(T[-1])

# where the camera is: zoom, and where his head lands on the page (it is at 620, 962 in the drawing)
BASE, CORNER, GROUP = (1.0, 620.0, 962.0), (0.42, 790.0, 1481.0), (0.92, 330.0, 1143.0)
ALERT = (300.0, 385.0)  # the alert in his head: where it is on the page, over him


def close(z):
    """Close on the alert, at zoom z: it fills the page, a little above the middle."""
    return (z, 540.0 + (620.0 - ALERT[0]) * z, 900.0 + (962.0 - ALERT[1]) * z)


CIRCLED, PULL, LIGHT = (2.95, 3.55), (4.4, 5.5), (6.45, 6.8)  # « Annuler » circled; the camera pulls back; his phone lights up
CAMERA = [(0.0, close(2.0)), (PULL[0], close(2.12)), (PULL[1], BASE), (T[2], BASE), (T[2] + 1.1, CORNER), (T[3], CORNER), (T[3] + 0.9, BASE),
          (T[5] + 0.1, BASE), (T[5] + 1.0, GROUP)]
# his face: where he looks (across, down), how open his lids are, his smile, his worry
FACE = [(0.0, (0.0, 1.0, 12.0, 0.0, 0.0)), (T[1] + 0.1, (0.0, 1.0, 12.0, 0.0, 0.0)), (T[1] + 0.35, (0.12, -0.3, 13.5, 0.0, 0.0)),
        (T[1] + 0.5, (0.12, -0.3, 13.5, 0.0, 0.0)), (T[1] + 0.9, (0.12, -0.3, 13.5, 0.3, 0.0)), (T[2], (0.12, -0.3, 13.5, 0.3, 0.0)),
        (T[2] + 0.3, (0.0, 1.0, 12.0, 0.0, 0.1)), (T[2] + 0.8, (0.0, 1.0, 12.0, 0.0, 0.35)), (T[3] + 1.0, (0.0, 1.0, 12.0, 0.0, 0.35)),
        (T[3] + 1.3, (0.15, -1.1, 13.0, -0.25, 0.45)), (T[4] + 0.15, (0.15, -1.1, 13.0, -0.25, 0.45)),
        (T[4] + 0.4, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[5] + 0.6, (-0.9, -0.35, 12.5, -0.3, 0.6)), (T[5] + 0.9, (0.95, -0.6, 13.0, -0.15, 0.4))]
BLINKS = [LIGHT[1] + 0.15, T[5] + 2.25]
TRAIL = [(456, 724, 12), (414, 692, 22), (345, 625, 50)]  # the first drawing's little bubbles, from his head up to the alert
GROUP_PEOPLE = [(850, 770, 0.5, "short", (-0.6, 0.2), "talk", True), (690, 800, 0.5, "long", (0.8, 0.1), "smile", False),
                (1004, 815, 0.5, "curly", (-0.9, 0.1), "smile", False)]
CAP = dict(font="futural", size=32, line=52, top=128, width=960)


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


def spaced_width(ln):
    return letters.width(ln, CAP["font"], CAP["size"]) + CAP["size"] * 0.12 * len(ln)


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


def chunks(text):
    """A line cut where he pauses (after « … », or where a sentence ends): each piece is written on its own."""
    out, cur = [], []
    for word in text.split(" "):
        cur.append(word)
        if word.endswith(("…", ".", "?", "!")):
            out.append(cur)
            cur = []
    return out + ([cur] if cur else [])


def caption(pen, t):
    """The line being said, written by hand at the top, word by word as it would be said, a piece at a time."""
    if t < 0.25:
        return  # the very first image: the alert alone
    i = max(k for k in range(len(LINES)) if T[k] <= t)
    pieces = chunks(LINES[i][0].upper())
    starts, at = [], T[i] + 0.1
    for piece in pieces:
        for _ in piece:
            starts.append(at)
            at += 1 / WPS
        at += PAUSE
    said = 1 + sum(1 for s_ in starts[1:] if s_ <= t)  # (its first word as soon as the line starts)
    for k, piece in enumerate(pieces):
        if said <= len(piece) or k == len(pieces) - 1:
            break
        said -= len(piece)
    said = min(said, len(piece))  # once all said, the last piece stays whole
    text = " ".join(piece)
    n = 0
    for li, ln in enumerate(balanced(text)):
        gap = CAP["size"] * 0.12
        x = 540 - spaced_width(ln) / 2
        y = CAP["top"] + li * CAP["line"]
        for word in ln.split(" "):
            if n >= said:
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

    # « …ou par peur de déranger »: further off, three people talking at their table, sliding in as the camera moves
    if t >= T[5] + 0.1:
        dx = 560 * (1 - ease(seg(t, T[5] + 0.1, T[5] + 1.0)))
        for k, (x, y, s, hair, look, mouth, beard) in enumerate(GROUP_PEOPLE):
            if k == 0 and mouth == "talk" and t >= T[5] + 1.0 and int((t - T[5]) * 4) % 2:
                mouth = "flat"  # he talks
            person(pen, x + dx, y, s, hair, look, mouth, beard, rng=steady(30 + k))
        back_table(pen, 1012, 560 + dx, 1120 + dx)
        b = pop(seg(t, T[5] + 1.0, T[5] + 1.3))
        if b > 0.05:
            speech(pen, 852 + dx, 560, 108 * b, 66 * b, grown(852 + dx, 560, (846 + dx, 650), b), "talk", rng=steady(40))

    # Tony at his table, through the camera
    z, qx, qy = camera(t)
    lx, ly, lids, smile, worry = keyed(FACE, t)
    blink = any(b <= t < b + 2 / DRAWINGS for b in BLINKS)
    with framed([z, 620.0, 962.0, qx, qy]):
        table(pen, wide=True)
        body(pen)
        head(pen, steady(1), hx=620.0, hy=962.0, tilt=6.0, look=(lx, ly), lids=lids, smile=smile, worry=worry, blink=blink)
        phone_on_table(pen, orange, glow=0.9 + 0.07 * math.sin(2 * math.pi * t / 1.6), rng=steady(2), lit=ease(seg(t, *LIGHT)))

        # « Toi aussi, t'as peur de déranger ? Moi, tout le temps. »: seen close, the alert in his head, « Annuler »
        # circled; « Et pourtant… »: the camera pulls back, it is a thought over him; « Moi c'est Tony »: it goes
        gone = 1 - ease(seg(t, T[1], T[1] + 0.25))
        if gone > 0.05:
            for k, (bx, by, r) in enumerate(TRAIL):
                bubble(pen, bx, by, r * gone, None, rng=steady(10 + k))
            alert(pen, *ALERT, s=gone, circled=seg(t, *CIRCLED), rng=steady(80))

    # « …renfermé »: seen from far off, he is shut in his own bubble; what is outside it goes
    if T[2] + 1.0 <= t < T[3]:
        k = 2.4 + (1.0 - 2.4) * ease(seg(t, T[2] + 1.0, T[2] + 1.7))
        if k < 2.3:
            inside = Image.new("L", img.size, 0)
            ImageDraw.Draw(inside).ellipse([(782 - 252 * k) * S, (1594 - 274 * k) * S, (782 + 252 * k) * S, (1594 + 274 * k) * S], fill=255)
            for layer in (img, orange):
                layer.paste(0, (0, 0), ImageOps.invert(inside))
        ring = loop_pts(steady(20), 782, 1594, 262, 282)
        n = int(len(ring) * ease(seg(t, T[2] + 1.0, T[2] + 1.7)))
        if n > 1:
            pen.line(ring[:n], w=3.4, over=0.0, breaks=False, drift=0.8, again=0.0)
        if t >= T[2] + 1.7:
            pen.line(loop_pts(steady(21), 782, 1594, 256, 290), w=1.8, over=0.0, breaks=False, drift=0.8, again=0.0)

    # « …n'osait pas poser de questions »: a question comes up out of his head and gets stuck there, squashed
    if T[3] + 1.0 <= t < T[4] + 0.2:
        up = pop(seg(t, T[3] + 1.0, T[3] + 1.4)) * (1 - ease(seg(t, T[4], T[4] + 0.2)))
        squash = 1 - 0.26 * ease(seg(t, T[3] + 1.6, T[3] + 1.8))
        shake = (2 if int(t * DRAWINGS) % 2 else -2) if t >= T[3] + 1.8 else 0
        if up > 0.05:
            bubble(pen, 656 + shake, 700 - 76 * up, 80 * up, "?", squash=squash, rng=steady(50))
        if T[3] + 1.8 <= t < T[4]:
            for sx in (-1, 1):  # it strains
                pen.line([(656 + sx * 100, 598), (656 + sx * 112, 612), (656 + sx * 112, 638), (656 + sx * 100, 652)], w=2.2, over=0.0, again=0.0)

    # « Peut-être par peur de dire n'importe quoi… »: what he would say, tangling itself in a speech bubble
    if T[4] + 0.3 <= t < T[5] + 0.2:
        b = pop(seg(t, T[4] + 0.3, T[4] + 0.6)) * (1 - ease(seg(t, T[5], T[5] + 0.2)))
        if b > 0.05:
            speech(pen, 300, 560, 215 * b, 165 * b, grown(300, 560, (436, 900), b), "scribble", p=seg(t, T[4] + 0.55, T[4] + 2.2), rng=steady(60))

    # « …ou par peur de déranger »: his « … », that he keeps to himself
    if T[5] + 1.5 <= t < T[5] + 2.75:
        b = pop(seg(t, T[5] + 1.5, T[5] + 1.75)) * (1 - ease(seg(t, T[5] + 2.5, T[5] + 2.75)))
        if b > 0.05:
            speech(pen, 562, 878, 62 * b, 44 * b, grown(562, 878, (480, 1000), b), "dots", p=seg(t, T[5] + 1.6, T[5] + 2.1), rng=steady(70))

    caption(pen, t)
    return finish(img, orange, v)


def _render(args):
    g, d = args
    frame_at(g / DRAWINGS, g % 3).save(f"{d}/{g:05d}.png")
    return g


def main(until=END):
    out = ROOT / "renders" / "film_v3.mp4"
    out.parent.mkdir(exist_ok=True)
    n = int(min(until, END) * DRAWINGS)
    with tempfile.TemporaryDirectory() as d:
        with Pool(4) as pool:
            for i, _ in enumerate(pool.imap_unordered(_render, [(g, d) for g in range(n)], chunksize=2)):
                if i % 48 == 0:
                    print(f"{i}/{n}", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(DRAWINGS), "-i", f"{d}/%05d.png", "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
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
