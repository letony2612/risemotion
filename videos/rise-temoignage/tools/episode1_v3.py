"""Tony's testimony, episode 1, v3: v2 with moving transitions and hand-drawn words.

v2: the full script, told as one story (the user's own words, reworked together).

Until Tony records it, the words show one phrase at a time, white on black like his earlier testimony video,
at the pace of someone speaking (~3 words a second). Drawn scenes follow the story:
A the hook: everyone else's chat bubbles around a lit phone, his own stays « … »;
B him at night, head in his hand;
C the report card, a teacher's red ink (never read aloud);
D a shell closes over him; inside, it gets darker;
E many small shells: other Christians, each alone in a corner;
F the phone lights with the RISE flame: a question, a prayer, a group, a message;
G the shells come together, light between them;
H the RISE logo animation on black, its boom, « Élevons-nous ensemble. »
v3: no hard cuts. The report card lies on the table by him; the camera dives into it, and pulls back out of it
as the shell begins; the other scenes cross over with a small push of the camera, and every shot drifts in a
little. The words are hand-lettered (Patrick Hand), white with a dark edge, and boil with the drawing; the
teacher writes in Caveat.
Usage: python3 tools/episode1_v3.py [t ...]  -> renders/episode1_v3.mp4, or stills at the given times
"""
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

import draw_test as dt
import episode1 as ep
from draw_test import Pen, arc, bez

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
W, H, S, FPS = 1080, 1920, dt.S, 24
TEXT_FONT = ImageFont.truetype(str(ROOT / "assets/fonts/patrick-hand-latin-400-normal.woff"), 78)
ep.HAND_FONT = ImageFont.truetype(str(ROOT / "assets/fonts/caveat-latin-700-normal.woff"), 96)
ep.INK, ep.INK_ORDER, ep.INK_LINES = ep.handwriting()  # the teacher's hand, again, in Caveat
FLAME = (255, 109, 0)
SPLASH = REPO / "videos/rise-ugc/assets/brand/rise_splash_dark.webm"
BOOM = REPO / "videos/rise-ugc/music/boom.wav"
WPS, PAUSE = 3.0, 0.3  # words a second, and the breath after each phrase

# (the words on screen, the scene under them)
SCRIPT = [
    ("J'ai créé un réseau social…", "A"),
    ("…alors que j'ose même pas parler aux gens.", "A"),
    ("Moi c'est Tony.", "B"),
    ("Et je suis le genre de personne qui ose pas aller vers les autres.", "B"),
    ("Qui ose pas poser de questions.", "B"),
    ("Peut-être par peur de dire n'importe quoi…", "B"),
    ("…ou peut-être par peur de déranger.", "B"),
    ("Depuis tout jeune, j'ai souvent été rabaissé.", "C"),
    ("Par des amis, par des profs…", "C"),
    ("…parfois même par des proches.", "C"),
    ("Alors j'ai appris à me faire petit.", "D"),
    ("À garder mes idées pour moi.", "D"),
    ("Avec le temps, c'est devenu une carapace.", "D"),
    ("Elle me protège…", "D"),
    ("…mais elle m'empêche aussi d'aller vers les autres.", "D"),
    ("Et c'est pareil dans ma foi.", "D"),
    ("J'avais des questions, des choses à partager…", "D"),
    ("…mais je les gardais pour moi.", "D"),
    ("Et je sais que je suis pas le seul.", "E"),
    ("Beaucoup de chrétiens vivent leur foi seuls, dans leur coin.", "E"),
    ("Alors j'ai créé RISE.", "F"),
    ("Un réseau social pour les chrétiens,", "F"),
    ("où tu peux poser tes questions,", "F?"),
    ("demander une prière, même en anonyme,", "Fp"),
    ("rejoindre des groupes, discuter en privé…", "Fg"),
    ("Sans avoir besoin de prendre la parole devant tout le monde.", "F"),
    ("Un endroit pour ceux qui, comme moi,", "G"),
    ("ont du mal à aller vers les autres.", "G"),
    ("Élevons-nous ensemble.", "H"),
]
END_HOLD = 2.8


def timeline():
    out, t = [], 0.0
    for text, scene in SCRIPT:
        d = max(1.3, len(text.split()) / WPS) + PAUSE
        out.append(dict(text=text, scene=scene, t0=t, t1=t + d))
        t += d
    out[-1]["t1"] += END_HOLD
    return out


LINES = timeline()
DURATION = LINES[-1]["t1"]


def span(scene):
    sel = [l for l in LINES if l["scene"].startswith(scene)]
    return sel[0]["t0"], sel[-1]["t1"]


def ease(x):
    return ep.ease(x)


def wrap(text, width=900):
    words, lines, cur = text.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if TEXT_FONT.getlength(nxt) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    lines.append(cur)
    return lines


def text_layer(text, variant):
    """The words, lettered by hand: white with a dark edge, each line a little off, a bit different 8 times a second."""
    lines = wrap(text)
    rng = np.random.default_rng(hash((text, variant)) % 2 ** 32)
    im = Image.new("RGBA", (W, 100 * len(lines) + 40), (0, 0, 0, 0))
    for i, line in enumerate(lines):
        ln = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
        x = (W - TEXT_FONT.getlength(line)) / 2
        fill = FLAME + (255,) if "RISE" in line and len(line) < 30 else (255, 255, 255, 255)
        ImageDraw.Draw(ln).text((x, 15), line, font=TEXT_FONT, fill=fill, stroke_width=7, stroke_fill=(0, 0, 0, 255))
        ln = ln.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC)
        im.alpha_composite(ln, (int(rng.uniform(-3, 3)), int(i * 100 + rng.uniform(-3, 3))))
    return im


TEXTS = {(l["text"], v): text_layer(l["text"], v) for l in LINES for v in range(3)}


def mini_shell(pen, cx, cy, s, light=0.0):
    """A small person (head, shoulders) under a small hatched dome."""
    pen.line(arc(cx, cy - 70 * s, 26 * s, 28 * s, 0, 360, 30), w=3)
    pen.line(bez((cx - 60 * s, cy + 40 * s), (cx - 50 * s, cy - 20 * s), (cx + 50 * s, cy - 20 * s), (cx + 60 * s, cy + 40 * s)), w=3)
    rx, ry, band = 120 * s, 170 * s, 24 * s
    outer = arc(cx, cy + 40 * s, rx, ry, 180, 360, 30)
    inner = arc(cx, cy + 40 * s, rx - band, ry - band, 360, 180, 30)
    pen.line(outer, w=3)
    pen.line(inner[::-1], w=2.2)
    for j in range(1, 12):
        a = math.radians(180 + j * 15)
        pen.line([(cx + (rx - band) * math.cos(a), cy + 40 * s + (ry - band) * math.sin(a)),
                  (cx + rx * math.cos(a), cy + 40 * s + ry * math.sin(a))], w=1.5, amp=0.4)
    pen.line([(cx - rx - 10, cy + 40 * s), (cx + rx + 10, cy + 40 * s)], w=3)
    if light > 0:  # a little flame lit above
        fx, fy = cx, cy - 175 * s
        pen.line(bez((fx, fy - 30 * light), (fx + 20, fy), (fx + 14, fy + 20), (fx, fy + 20))
                 + bez((fx, fy + 20), (fx - 14, fy + 20), (fx - 20, fy), (fx, fy - 30 * light))[1:], w=3)


CROWD = [(220, 700), (760, 640), (480, 980), (180, 1300), (820, 1260)]


def crowd(variant, t, gather):
    img, pen = ep.pen_for(variant, 7)
    g = ease(gather)
    for k, (x, y) in enumerate(CROWD):
        tx, ty = 200 + k * 170, 1150 + (40 if k % 2 else 0)  # side by side, at the end
        cx, cy = x + (tx - x) * g, y + (ty - y) * g
        bob = 6 * math.sin(t * 2 + k)
        mini_shell(pen, cx, cy + bob, 0.95 - 0.35 * g, light=g)
    if g > 0.6:  # light between them
        for k in range(40):
            a = math.radians(k * 9 + pen.rng.uniform(-3, 3))
            r0, r1 = 140, 140 + 260 * (g - 0.6) / 0.4 * pen.rng.uniform(0.5, 1)
            pen.line([(540 + r0 * math.cos(a), 760 + r0 * 0.6 * math.sin(a)), (540 + r1 * math.cos(a), 760 + r1 * 0.6 * math.sin(a))], w=1.4, amp=0.4)
        fx, fy = 540, 760
        pen.line(bez((fx, fy - 70), (fx + 50, fy - 10), (fx + 38, fy + 40), (fx, fy + 40)) + bez((fx, fy + 40), (fx - 38, fy + 40), (fx - 50, fy - 10), (fx, fy - 70))[1:], w=5)
    return img


def icon(pen, kind, cx, cy):
    if kind == "?":
        pen.line(arc(cx, cy - 50, 55, 55, 200, 400, 30) + [(cx, cy + 40)], w=9)
        pen.d.ellipse([(cx - 10) * S, (cy + 80) * S, (cx + 10) * S, (cy + 100) * S], fill=255)
    elif kind == "p":  # a candle: a prayer
        pen.line([(cx - 30, cy + 110), (cx - 30, cy - 10), (cx + 30, cy - 10), (cx + 30, cy + 110)], w=6)
        pen.line(bez((cx, cy - 110), (cx + 40, cy - 60), (cx + 30, cy - 25), (cx, cy - 25)) + bez((cx, cy - 25), (cx - 30, cy - 25), (cx - 40, cy - 60), (cx, cy - 110))[1:], w=6)
    elif kind == "g":  # a group, and a private chat
        for dx, r in ((-80, 34), (0, 42), (80, 34)):
            pen.line(arc(cx + dx, cy - 40, r, r, 0, 360, 30), w=5)
            pen.line(bez((cx + dx - r * 1.5, cy + 70), (cx + dx - r, cy + 10), (cx + dx + r, cy + 10), (cx + dx + r * 1.5, cy + 70)), w=5)
        pen.line(arc(cx + 30, cy + 170, 90, 40, 0, 360, 40), w=4)
        pen.line(arc(cx - 40, cy + 240, 80, 36, 0, 360, 40), w=4)


def phone(variant, t, kind):
    img, pen = ep.pen_for(variant, 8)
    px, py, pw, ph = 540, 1080, 520, 980
    body = [(px - pw / 2, py - ph / 2), (px + pw / 2, py - ph / 2), (px + pw / 2, py + ph / 2), (px - pw / 2, py + ph / 2)]
    pen.line(body + body[:1], w=6)
    pen.line([(px - 50, py - ph / 2 + 30), (px + 50, py - ph / 2 + 30)], w=5)
    for a in np.linspace(0, 360, 110, endpoint=False):
        ra = math.radians(a + pen.rng.uniform(-2, 2))
        r0 = 560 + pen.rng.uniform(0, 30)
        r1 = r0 + pen.rng.uniform(40, 120) * (0.8 + 0.2 * math.sin(t * 2.5))
        pen.line([(px + r0 * 0.55 * math.cos(ra), py + r0 * math.sin(ra)), (px + r1 * 0.55 * math.cos(ra), py + r1 * math.sin(ra))], w=1.3, amp=0.4)
    if kind is None:  # the RISE flame, big
        fx, fy = px, py
        pen.line(bez((fx, fy - 150), (fx + 120, fy - 20), (fx + 95, fy + 100), (fx, fy + 100)) + bez((fx, fy + 100), (fx - 95, fy + 100), (fx - 120, fy - 20), (fx, fy - 150))[1:], w=7)
        pen.line(bez((fx, fy - 40), (fx + 45, fy + 10), (fx + 30, fy + 60), (fx, fy + 60)) + bez((fx, fy + 60), (fx - 30, fy + 60), (fx - 45, fy + 10), (fx, fy - 40))[1:], w=4)
    else:
        icon(pen, kind, px, py - 40)
    return img


_splash = {}


def splash_frame(t):
    """The official RISE logo animation (dark version), from 0.2 s in, scaled into the frame."""
    if "dir" not in _splash:
        d = tempfile.mkdtemp()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-ss", "0.2", "-i", str(SPLASH), "-r", str(FPS), f"{d}/%04d.png"], check=True)
        _splash["dir"] = d
        _splash["n"] = len(list(Path(d).glob("*.png")))
    k = max(1, min(_splash["n"], int(t * FPS) + 1))
    im = Image.open(f'{_splash["dir"]}/{k:04d}.png').convert("RGBA")
    return im.resize((int(im.width * 0.9), int(im.height * 0.9)), Image.LANCZOS)


PAPER = [(468, 1505), (742, 1490), (768, 1640), (448, 1652)]  # on the table, in the scene's own place
PAPER_C = (615, 1690)  # its middle, once the scene is lowered


def with_paper(g, variant):
    """The report card, lying on the table next to him."""
    img, pen = ep.pen_for(variant, 9)
    pen.poly(PAPER, fill=0)
    pen.line(PAPER + PAPER[:1], w=3.5)
    for k in range(4):
        y0 = 1520 + k * 18
        pen.line([(485, y0), (720 - k * 2, y0 - 6)], w=1.6)
    pen.line([(480, 1600), (740, 1592), (748, 1630), (472, 1638), (480, 1600)], w=1.8)
    paper = img.resize((W, H), Image.LANCZOS)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(PAPER, fill=255)
    out = Image.composite(paper, g, m)
    out = Image.composite(paper, out, paper.point(lambda v: 255 if v > 40 else 0))
    rgb = out.convert("RGB")
    ImageDraw.Draw(rgb).line([(492, 1612), (530, 1606), (560, 1614), (600, 1604), (650, 1612), (700, 1606)], fill=(226, 40, 40), width=3)
    return rgb


def lower(im, dy=120):
    """His scenes sit a little lower, to leave the top to the words."""
    out = Image.new("RGB", (W, H), 0)
    out.paste(im, (0, dy))
    return out


def scene_image(scene, f, t, cache):
    variant = (f // 3) % 3
    key = (scene[0], f - f % 3)

    def cached(name, fn):
        if cache.get(name, (None,))[0] != key:
            cache[name] = (key, fn())
        return cache[name][1]

    s = scene[0]
    if s == "A":
        return cached("A", lambda: ep.scene1(variant, t).resize((W, H), Image.LANCZOS)).convert("RGB")
    if s in "BD":
        g = cached("tony", lambda: dt.draw(variant, t))
        if s == "B":
            return lower(with_paper(g, variant))
        d0, d1 = span("D")
        ep.S4 = d0 - 0.25  # the shell's plates start with the scene
        sh = cached("shell", lambda: ep.shell(variant, t).resize((W, H), Image.LANCZOS))
        faith = [l for l in LINES if l["text"].startswith("Et c'est pareil")][0]["t0"]
        dim = 1.0 - 0.45 * ease((t - faith + 0.5) / 1.2)
        g = Image.eval(g, lambda v: int(v * dim))
        g = with_paper(g, variant)
        shm = sh.point(lambda v: 255 if v > 0 else 0)
        return lower(Image.composite(sh.convert("RGB"), g, shm))
    if s == "C":
        c0, c1 = span("C")
        ep.WRITE0, ep.WRITE1 = c0 + 0.9, c0 + 3.4
        if f"card{variant}" not in cache:
            cache[f"card{variant}"] = ep.report_card(variant)
        slide = 0  # the camera brings it in now
        base = Image.new("RGB", (W, H), 0)
        base.paste(cache[f"card{variant}"].convert("RGB"), (0, int(slide)))
        ink = ep.ink_at(t)
        if ink is not None:
            base.paste(ink, (0, int(slide)), ink)
        return base
    if s == "E":
        return cached("E", lambda: crowd(variant, t, 0).resize((W, H), Image.LANCZOS)).convert("RGB")
    if s == "F":
        kind = {"F?": "?", "Fp": "p", "Fg": "g"}.get(scene)
        return cached("F" + scene, lambda: phone(variant, t, kind).resize((W, H), Image.LANCZOS)).convert("RGB")
    if s == "G":
        g0, g1 = span("G")
        return cached("G", lambda: crowd(variant, t, (t - g0) / (g1 - g0 - 0.6)).resize((W, H), Image.LANCZOS)).convert("RGB")
    h0, _ = span("H")
    base = Image.new("RGB", (W, H), 0)
    sp = splash_frame(t - h0)
    base.paste(sp, ((W - sp.width) // 2, 760 - sp.height // 2), sp)
    return base


def cam(img, scale, cx, cy, to=None):
    """The camera: scaled by scale, the point (cx, cy) brought to `to` (where it is, by default)."""
    qx, qy = to or (cx, cy)
    if abs(scale - 1) < 1e-3 and (qx, qy) == (cx, cy):
        return img
    a = 1 / scale
    return img.transform((W, H), Image.AFFINE, (a, 0, cx - qx * a, 0, a, cy - qy * a), resample=Image.BILINEAR)


def toward(u):
    """Where the report card's middle is on screen as the camera dives: from the table to the middle."""
    return (PAPER_C[0] + (540 - PAPER_C[0]) * u, PAPER_C[1] + (1000 - PAPER_C[1]) * u)


GROUPS = []  # (group letter, start, end)
for l in LINES:
    g = l["scene"][0]
    if GROUPS and GROUPS[-1][0] == g:
        GROUPS[-1][2] = l["t1"]
    else:
        GROUPS.append([g, l["t0"], l["t1"]])
X = 0.4  # half a cross-over


def shot(g, f, t, cache):
    """A group's picture at t, with its slow drift in."""
    line = next((l for l in LINES if l["scene"][0] == g and l["t0"] <= t < l["t1"]), None)
    if line is None:
        line = min((l for l in LINES if l["scene"][0] == g), key=lambda l: min(abs(t - l["t0"]), abs(t - l["t1"])))
    img = scene_image(line["scene"], f, t, cache)
    g0, g1 = next((a, b) for x, a, b in GROUPS if x == g)
    if g == "H":
        return img
    return cam(img, 1 + 0.045 * min(1, max(0, (t - g0) / (g1 - g0))), 540, 960)


def picture(f, t, cache):
    for i in range(len(GROUPS) - 1):
        (ga, a0, a1), (gb, b0, b1) = GROUPS[i], GROUPS[i + 1]
        tb = a1
        if (ga, gb) == ("B", "C") and tb - 1.1 <= t < tb + 0.3:  # dive into the report card on the table
            u = ease((t - (tb - 1.1)) / 1.2)
            A = cam(shot("B", f, t, cache), 1 + 6.5 * u ** 1.6, *PAPER_C, to=toward(min(1, u * 1.6)))
            k = min(1, max(0, (u - 0.55) / 0.4))
            if k <= 0:
                return A
            B = cam(shot("C", f, t, cache), 1.25 - 0.25 * k, 540, 1000)
            return Image.blend(A, B, k)
        if (ga, gb) == ("C", "D") and tb - 0.3 <= t < tb + 0.9:  # and back out of it
            u = ease((t - (tb - 0.3)) / 1.2)
            B = cam(shot("D", f, t, cache), 7.5 - 6.5 * u ** 0.6, *PAPER_C, to=toward(1 - min(1, u * 1.3)))
            k = min(1, u / 0.45)
            A = cam(shot("C", f, t, cache), 1 + 0.3 * u, 540, 1000)
            return Image.blend(A, B, k)
        if abs(t - tb) < X and (ga, gb) not in (("B", "C"), ("C", "D")):  # cross over with a small push
            k = (t - (tb - X)) / (2 * X)
            A = cam(shot(ga, f, t, cache), 1 + 0.12 * k, 540, 960)
            B = cam(shot(gb, f, t, cache), 1.12 - 0.12 * k, 540, 960)
            return Image.blend(A, B, ease(k))
    g = next(x for x, a, b in GROUPS if a <= t < b) if t < GROUPS[-1][2] else "H"
    return shot(g, f, t, cache)


def frame(f, cache):
    t = f / FPS
    variant = (f // 3) % 3
    line = next(l for l in LINES if l["t0"] <= t < l["t1"] or l is LINES[-1])
    base = picture(f, t, cache).convert("RGBA")
    tl = TEXTS[(line["text"], variant)]
    if line["scene"] == "H":
        a = ease((t - line["t0"] - 0.9) / 0.5)  # the slogan after the boom
        y = 1040
    else:
        a = ease((t - line["t0"]) / 0.15)
        y = 150
    if a > 0:
        if a < 1:
            tl = tl.copy()
            tl.putalpha(tl.getchannel("A").point(lambda v: int(v * a)))
        base.alpha_composite(tl, (0, y))
    return base.convert("RGB")


def sound(path):
    sr = 48000
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-t", str(DURATION), "-i", str(ep.MUSIC), "-ac", "2", "-ar", str(sr), f"{d}/m.wav"], check=True)
        m, _ = sf.read(f"{d}/m.wav", always_2d=True)
    n = int(DURATION * sr)
    m = np.pad(m, ((0, max(0, n - len(m))), (0, 0)))[:n]
    t = np.arange(n) / sr
    h0, _ = span("H")
    env = np.clip(t / 0.5, 0, 1) * np.clip((h0 - t) / 0.4, 0, 1) * 0.5  # a bed under the voice to come; silence for the logo
    y = m * env[:, None]
    boom, _ = sf.read(BOOM, always_2d=True)
    at = int((h0 + 0.467) * sr)
    k = min(len(boom), n - at)
    y[at:at + k] += 0.8 * boom[:k]
    y /= max(1.0, np.max(np.abs(y)) / 0.89)
    sf.write(path, y, sr)


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        cache = {}
        for f in range(int(DURATION * FPS)):
            frame(f, cache).save(f"{d}/{f:05d}.png")
        sound(f"{d}/a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{d}/%05d.png", "-i", f"{d}/a.wav",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(out / "episode1_v3.mp4")], check=True)
    print(out / "episode1_v3.mp4", f"{DURATION:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        c = {}
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS), c).save(ROOT / f"still_{s}.png")
    else:
        main()
