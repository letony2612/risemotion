"""Tony's testimony, episode 1: « J'ai créé un réseau social… alors que j'ose même pas parler aux gens. »

White ink on black, drawn by code (draw_test.py's pen), the lines boiling 8 times a second. Text on screen in
TikTok's style until Tony records his voice. The scenes:
1. the hook: chat bubbles of other people pop up all around a lit phone; his own bubble stays « … »;
2. « Moi c'est Tony. »: him at night, head in his hand (the test scene);
3. the report card slides in, and a teacher's red ink writes « Tony se complaît dans sa médiocrité. »,
   in silence but for the pen;
4. a shell closes over him, plate by plate: « Des profs, des « amis », des proches… alors je me suis renfermé. »;
5. inside the shell, dimmer: « Une carapace que j'ai encore aujourd'hui. » … « Partie 2 ».
Usage: python3 tools/episode1.py  -> renders/episode1.mp4
"""
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import butter, sosfilt

import draw_test as dt
from draw_test import Pen, arc, bez

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
W, H, S, FPS = 1080, 1920, dt.S, 24
DURATION = 24.0
CAP_FONT = ImageFont.truetype(str(REPO / "videos/rise-ugc/assets/fonts/FreeSansBold.ttf"), 58)
HAND_FONT = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf", 82)
PRINT_FONT = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 34)
RED = (226, 40, 40)
MUSIC = REPO / "videos/rise-presentation/assets/audio/music_track.mp3"

# when each thing happens (s)
S1, S2, S3, S4, S5 = 0.0, 4.5, 8.0, 14.0, 19.5
WRITE0, WRITE1 = 10.0, 12.6  # the teacher's pen
CAPTIONS = [  # (from, to, text, y of its middle)
    (0.15, 2.3, "J'ai créé un\nréseau social…", 330),
    (2.3, 4.5, "…alors que j'ose même\npas parler aux gens.", 330),
    (4.6, 6.3, "Moi c'est Tony.", 150),
    (6.3, 8.0, "Et ça, c'est\nmon histoire.", 150),
    (8.3, 10.0, "À l'école, un prof\na écrit ça sur mon bulletin :", 300),
    (14.0, 16.7, "Des profs, des « amis »,\ndes proches…", 150),
    (16.7, 19.5, "Alors je me suis\nrenfermé.", 150),
    (19.6, 22.4, "Une carapace que j'ai\nencore aujourd'hui.", 150),
    (22.4, 24.0, "Partie 2 →", 150),
]


def ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def caption(text):
    """TikTok's text: black words on white, one rounded box per line."""
    lines = text.split("\n")
    pad, lh = 22, 76
    widths = [CAP_FONT.getlength(t) for t in lines]
    im = Image.new("RGBA", (int(max(widths)) + 2 * pad + 8, lh * len(lines) + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (t, w) in enumerate(zip(lines, widths)):
        x0 = (im.width - w) / 2 - pad
        d.rounded_rectangle([x0, i * lh + 2, x0 + w + 2 * pad, i * lh + lh + 6], 16, fill=(255, 255, 255, 255))
        d.text((x0 + pad, i * lh + 8), t, font=CAP_FONT, fill=(18, 18, 18, 255))
    return im


CAP_IMG = {c[2]: caption(c[2]) for c in CAPTIONS}


def pen_for(variant, seed, size=(W * S, H * S)):
    img = Image.new("L", size, 0)
    return img, Pen(img, np.random.default_rng(seed * 10 + variant))


# --- scene 1: the hook
CHATS = [  # x, y, w, h, appears at, side the tail is on, lines
    (90, 560, 360, 150, 0.2, -1, 3), (640, 520, 340, 130, 0.5, 1, 2), (130, 790, 300, 120, 0.9, -1, 2),
    (700, 760, 300, 150, 1.2, 1, 3), (60, 1010, 330, 120, 1.6, -1, 2), (720, 1000, 320, 130, 1.9, 1, 2),
    (150, 1230, 280, 110, 2.4, -1, 2), (740, 1230, 290, 120, 2.8, 1, 2)]


def scene1(variant, t):
    img, pen = pen_for(variant, 1)
    # the phone, lit, in the middle
    px, py, pw, ph = 540, 1280, 330, 620
    body = [(px - pw / 2, py - ph / 2), (px + pw / 2, py - ph / 2), (px + pw / 2, py + ph / 2), (px - pw / 2, py + ph / 2)]
    pen.line(body + body[:1], w=5)
    pen.line([(px - 40, py - ph / 2 + 22), (px + 40, py - ph / 2 + 22)], w=4)
    for a in np.linspace(0, 360, 90, endpoint=False):  # its light, scratched out around it
        ra = math.radians(a + pen.rng.uniform(-2, 2))
        r0 = 330 + pen.rng.uniform(0, 30)
        r1 = r0 + pen.rng.uniform(40, 110) * (0.8 + 0.2 * math.sin(t * 2.5))
        pen.line([(px + r0 * 0.55 * math.cos(ra), py + r0 * math.sin(ra)), (px + r1 * 0.55 * math.cos(ra), py + r1 * math.sin(ra))], w=1.3, amp=0.4)
    fx, fy = px, py - 40  # the RISE flame on its screen
    pen.line(bez((fx, fy - 70), (fx + 60, fy - 10), (fx + 45, fy + 50), (fx, fy + 50)) + bez((fx, fy + 50), (fx - 45, fy + 50), (fx - 60, fy - 10), (fx, fy - 70))[1:], w=5)
    pen.line(bez((fx, fy - 20), (fx + 22, fy + 5), (fx + 15, fy + 30), (fx, fy + 30)) + bez((fx, fy + 30), (fx - 15, fy + 30), (fx - 22, fy + 5), (fx, fy - 20))[1:], w=3)
    # everyone else talking: bubbles pop up
    for k, (x, y, w, h, at, side, n) in enumerate(CHATS):
        p = ease((t - at) / 0.25)
        if p <= 0:
            continue
        s = 0.6 + 0.4 * p
        cx, cy = x + w / 2, y + h / 2
        ww, hh = w * s, h * s
        box = arc(cx, cy, ww / 2, hh / 2, 0, 360, 60)
        pen.line(box, w=3.5)
        tx = cx + side * ww * 0.3
        pen.line([(tx - 18, cy + hh * 0.45), (tx + side * 30, cy + hh * 0.5 + 34), (tx + 18, cy + hh * 0.45)], w=3)
        for i in range(n):  # their words: scribbles
            ly = cy - hh * 0.22 + i * hh * 0.22
            L = ww * (0.55 if i < n - 1 else 0.35)
            pts = [(cx - ww * 0.3 + j * L / 12, ly + 5 * math.sin(j * 1.7 + k)) for j in range(13)]
            pen.line(pts, w=2.4, amp=1.2)
    # his own bubble: empty, three dots that never become words
    if t > 0.4:
        cx, cy = 790, 1680
        pen.line(arc(cx, cy, 110, 62, 0, 360, 60), w=3.5)
        pen.line([(cx - 60, cy + 50), (cx - 95, cy + 95), (cx - 30, cy + 58)], w=3)
        for i in range(3):
            r = 9 + 3 * max(0, math.sin(t * 6 - i * 0.9))
            x = cx - 36 + 36 * i
            pen.d.ellipse([(x - r) * S, (cy - r) * S, (x + r) * S, (cy + r) * S], fill=255)
    return img


# --- scene 3: the report card
def report_card(variant):
    img, pen = pen_for(variant, 3)
    x0, y0, x1, y1 = 110, 520, 970, 1500
    pen.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], w=5)
    pen.line([(x0 + 40, y0 + 120), (x1 - 40, y0 + 120)], w=3)
    d = pen.d
    d.text(((x0 + 60) * S, (y0 + 40) * S), "BULLETIN SCOLAIRE", font=ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 46 * S), fill=255)
    rows = [("Français", "7"), ("Mathématiques", "5,5"), ("Histoire-Géo", "8"), ("Anglais", "6,5")]
    big = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 34 * S)
    for i, (m, n) in enumerate(rows):
        y = y0 + 170 + i * 85
        d.text(((x0 + 60) * S, y * S), m, font=big, fill=200)
        d.text(((x1 - 190) * S, y * S), n + " / 20", font=big, fill=200)
        pen.line([(x0 + 40, y + 62), (x1 - 40, y + 62)], w=1.6)
    pen.line([(x1 - 230, y0 + 150), (x1 - 230, y0 + 500)], w=2)
    ay = y0 + 540
    d.text(((x0 + 60) * S, ay * S), "Appréciation du professeur principal", font=big, fill=200)
    pen.line([(x0 + 40, ay + 60), (x1 - 40, ay + 60), (x1 - 40, y1 - 50), (x0 + 40, y1 - 50), (x0 + 40, ay + 60)], w=2.5)
    small = img.resize((W, H), Image.LANCZOS)
    return small.rotate(-3, resample=Image.BICUBIC, center=(540, 1000))


def handwriting():
    """The teacher's red ink, on its own layer (RGBA), and the x where each letter ends, to reveal it."""
    lines = ["Tony se complaît", "dans sa médiocrité."]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rng = np.random.default_rng(5)
    order = []
    for li, t in enumerate(lines):
        x, y = 190, 1180 + li * 105
        for ch in t:
            g = Image.new("RGBA", (130, 150), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((20, 10), ch, font=HAND_FONT, fill=RED + (255,))
            g = g.rotate(rng.uniform(-4, 4), resample=Image.BICUBIC)
            yy = y + rng.uniform(-3, 3)
            im.alpha_composite(g, (int(x - 20), int(yy - 10)))
            x += HAND_FONT.getlength(ch) * 0.98
            order.append((li, x))
    return im.rotate(-3, resample=Image.BICUBIC, center=(540, 1000)), order, lines


INK, INK_ORDER, INK_LINES = handwriting()


def ink_at(t):
    """The red ink written so far: letters appear one after the other over the pen's time."""
    n = len(INK_ORDER)
    k = int(n * ease((t - WRITE0) / (WRITE1 - WRITE0)) ** 0.8 + 0.5) if t > WRITE0 else 0
    if k <= 0:
        return None
    li, xe = INK_ORDER[k - 1]
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    if li == 0:
        d.rectangle([0, 1150, xe + 4, 1270], fill=255)
    else:
        d.rectangle([0, 1150, W, 1262], fill=255)
        d.rectangle([0, 1262, xe + 4, 1380], fill=255)
    mask = mask.rotate(-3, resample=Image.BICUBIC, center=(540, 1000))
    out = INK.copy()
    out.putalpha(Image.composite(INK.getchannel("A"), Image.new("L", (W, H), 0), mask))
    return out


# --- scenes 4-5: the shell
PLATES = 11


def shell(variant, t):
    """Plates of a shell fly in and lock around him, one after the other."""
    img, pen = pen_for(variant, 4)
    cx, cy, rx, ry, band = 590, 1180, 500, 700, 85
    for k in range(PLATES):
        a0 = 180 + k * 180 / PLATES - 4
        a1 = 180 + (k + 1) * 180 / PLATES + 4
        p = ease((t - (S4 + 0.25 + k * 0.32)) / 0.45)
        if p <= 0:
            continue
        mid = math.radians((a0 + a1) / 2)
        off = (1 - p) * 700
        ox, oy = off * math.cos(mid), off * math.sin(mid)
        outer = [(x + ox, y + oy) for x, y in arc(cx, cy, rx, ry, a0, a1, 14)]
        inner = [(x + ox, y + oy) for x, y in arc(cx, cy, rx - band, ry - band, a1, a0, 14)]
        pen.poly(outer + inner, fill=0)
        pen.line(outer + inner + outer[:1], w=4.5)
        for j in range(1, 9):  # the plate's hatching
            u = j / 9
            aa = math.radians(a0 + (a1 - a0) * u)
            pen.line([(cx + ox + (rx - band + 8) * math.cos(aa), cy + oy + (ry - band + 8) * math.sin(aa)),
                      (cx + ox + (rx - 8) * math.cos(aa), cy + oy + (ry - 8) * math.sin(aa))], w=1.8, amp=0.6)
    # the sides come down to the table
    for side in (-1, 1):
        p = ease((t - (S4 + 0.25 + PLATES * 0.32)) / 0.5)
        if p <= 0:
            continue
        x_o, x_i = cx + side * rx, cx + side * (rx - band)
        top, bot = cy, cy + (1470 - cy) * p
        pen.poly([(x_o, top), (x_i, top), (x_i, bot), (x_o, bot)], fill=0)
        pen.line([(x_o, top), (x_o, bot)], w=4.5)
        pen.line([(x_i, top), (x_i, bot)], w=4.5)
        for y in np.arange(top + 30, bot, 34):
            pen.line([(x_o, y), (x_i, y + 10)], w=1.6, amp=0.5)
    return img


def frame(f, cache):
    t = f / FPS
    variant = (f // 3) % 3
    key = f - f % 3  # a new drawing every 3 frames
    if t < S2:
        if cache.get("k1") != key:
            cache["k1"], cache["s1"] = key, scene1(variant, t).resize((W, H), Image.LANCZOS)
        base = cache["s1"].convert("RGB")
    elif t < S3 or t >= S4:
        if cache.get("k2") != key:
            cache["k2"], cache["s2"] = key, dt.draw(variant, t)
        g = cache["s2"]
        if t >= S4:
            if cache.get("k4") != key:
                cache["k4"], cache["s4"] = key, shell(variant, t).resize((W, H), Image.LANCZOS)
            dim = 1.0 - 0.45 * ease((t - (S5 - 0.3)) / 1.2)  # inside the closed shell it gets darker
            g = Image.eval(g, lambda v: int(v * dim))
            g = Image.composite(cache["s4"], g, cache["s4"].point(lambda v: 255 if v > 0 else 0))
            mask = Image.new("L", (W, H), 0)
        base = g.convert("RGB")
    else:
        if f"card{variant}" not in cache:
            cache[f"card{variant}"] = report_card(variant)
        card = cache[f"card{variant}"]
        slide = (1 - ease((t - S3) / 0.6)) * 1400
        base = Image.new("RGB", (W, H), 0)
        base.paste(card.convert("RGB"), (0, int(slide)))
        ink = ink_at(t)
        if ink is not None:
            base.paste(ink, (0, int(slide)), ink)
    base = base.convert("RGBA")
    for a, b, text, y in CAPTIONS:
        if a <= t < b:
            im = CAP_IMG[text]
            pop = 0.88 + 0.12 * ease((t - a) / 0.18)
            im2 = im.resize((max(1, int(im.width * pop)), max(1, int(im.height * pop))), Image.BICUBIC)
            base.alpha_composite(im2, (int((W - im2.width) / 2), int(y - im2.height / 2)))
    return base.convert("RGB")


def sound(path):
    """The quiet start of the RISE track, cut off before the report card; the pen scratching in the silence;
    the music back, softer, under the shell."""
    sr = 48000
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-t", str(DURATION), "-i", str(MUSIC), "-ac", "2", "-ar", str(sr), f"{d}/m.wav"], check=True)
        m, _ = sf.read(f"{d}/m.wav", always_2d=True)
    n = int(DURATION * sr)
    m = np.pad(m, ((0, max(0, n - len(m))), (0, 0)))[:n]
    t = np.arange(n) / sr
    env = np.ones(n)
    env *= np.clip((S3 + 0.4 - t) / 0.6, 0, 1) + np.clip((t - S4) / 1.5, 0, 1) * 0.7  # out for the card, back for the shell
    env *= np.clip(t / 0.3, 0, 1) * np.clip((DURATION - t) / 1.0, 0, 1)
    y = m * env[:, None] * 0.9
    rng = np.random.default_rng(3)
    noise = sosfilt(butter(4, [1800, 6500], "bandpass", fs=sr, output="sos"), rng.standard_normal(n))
    pen = np.zeros(n)
    k = len(INK_ORDER)
    for i in range(k):  # one stroke of the pen per letter
        a = WRITE0 + (WRITE1 - WRITE0) * ((i / k) ** 1.25)
        i0 = int(a * sr)
        L = int(rng.uniform(0.05, 0.11) * sr)
        pen[i0:i0 + L] += np.sin(np.linspace(0, np.pi, L)) * rng.uniform(0.5, 1.0)
    y += (noise * pen * 0.18)[:, None]
    y /= max(1.0, np.max(np.abs(y)) / 0.89)
    sf.write(path, y, sr)


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        cache = {}
        for f in range(int(DURATION * FPS)):
            frame(f, cache).save(f"{d}/{f:04d}.png")
        sound(f"{d}/a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{d}/%04d.png", "-i", f"{d}/a.wav",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(out / "episode1.mp4")], check=True)
    print(out / "episode1.mp4")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:  # stills at the given times, to check
        c = {}
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS), c).save(ROOT / f"still_{s}.png")
    else:
        main()
