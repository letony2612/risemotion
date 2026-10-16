"""Tony's testimony, episode 1, v2: the full script, told as one story (the user's own words, reworked together).

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
Usage: python3 tools/episode1_v2.py [t ...]  -> renders/episode1_v2.mp4, or stills at the given times
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
TEXT_FONT = ImageFont.truetype(str(REPO / "videos/rise-ugc/assets/fonts/FreeSansBold.ttf"), 64)
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


def text_layer(text):
    lines = wrap(text)
    im = Image.new("RGBA", (W, 90 * len(lines) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        x = (W - TEXT_FONT.getlength(line)) / 2
        for dx, dy in ((0, 4), (2, 4), (-2, 4)):  # a soft shadow so the words read over white lines
            d.text((x + dx, 10 + i * 90 + dy), line, font=TEXT_FONT, fill=(0, 0, 0, 200))
        fill = FLAME + (255,) if "RISE" in line and len(line) < 30 else (255, 255, 255, 255)
        d.text((x, 10 + i * 90), line, font=TEXT_FONT, fill=fill)
    return im


TEXTS = {l["text"]: text_layer(l["text"]) for l in LINES}


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
    k = min(_splash["n"], int(t * FPS) + 1)
    im = Image.open(f'{_splash["dir"]}/{k:04d}.png').convert("RGBA")
    return im.resize((int(im.width * 0.9), int(im.height * 0.9)), Image.LANCZOS)


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
            return lower(g.convert("RGB"))
        d0, d1 = span("D")
        ep.S4 = d0 - 0.25  # the shell's plates start with the scene
        sh = cached("shell", lambda: ep.shell(variant, t).resize((W, H), Image.LANCZOS))
        faith = [l for l in LINES if l["text"].startswith("Et c'est pareil")][0]["t0"]
        dim = 1.0 - 0.45 * ease((t - faith + 0.5) / 1.2)
        g = Image.eval(g, lambda v: int(v * dim))
        return lower(Image.composite(sh, g, sh.point(lambda v: 255 if v > 0 else 0)).convert("RGB"))
    if s == "C":
        c0, c1 = span("C")
        ep.WRITE0, ep.WRITE1 = c0 + 0.9, c0 + 3.4
        if f"card{variant}" not in cache:
            cache[f"card{variant}"] = ep.report_card(variant)
        slide = (1 - ease((t - c0) / 0.6)) * 1400
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


def frame(f, cache):
    t = f / FPS
    line = next(l for l in LINES if l["t0"] <= t < l["t1"] or l is LINES[-1])
    base = scene_image(line["scene"], f, t, cache).convert("RGBA")
    if line["scene"] == "H":
        a = ease((t - line["t0"] - 0.9) / 0.5)  # the slogan after the boom
        if a > 0:
            tl = TEXTS[line["text"]].copy()
            tl.putalpha(tl.getchannel("A").point(lambda v: int(v * a)))
            base.alpha_composite(tl, (0, 1040))
    else:
        tl = TEXTS[line["text"]]
        a = ease((t - line["t0"]) / 0.15)
        if a < 1:
            tl = tl.copy()
            tl.putalpha(tl.getchannel("A").point(lambda v: int(v * a)))
        base.alpha_composite(tl, (0, 150))
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
                        "-movflags", "+faststart", str(out / "episode1_v2.mp4")], check=True)
    print(out / "episode1_v2.mp4", f"{DURATION:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        c = {}
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS), c).save(ROOT / f"still_{s}.png")
    else:
        main()
