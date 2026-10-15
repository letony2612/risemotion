"""The reel « rise. » — RISE in a few words, cut on the reference reel's own sound, then the logo.

The user sent the reference reel ("graphics / transitions / ideas / feelings / re / repe. / repea / repeat.")
and its audio: a run of whooshes that speed up. The reel keeps the reference's edit (the same 24 cuts at the
same times, each at the end of a whoosh; the light flips on every cut) and moves every word like a motion
designer would, on the whooshes:
- letters rising from their baseline, popping, dropping, closing up from wide tracking;
- words slamming in from close up, whipping or pushing in with motion blur, pulled into focus;
- a whoosh carried across a cut: the word leaves the way the next one arrives (zoom, whip, push).
The words follow the user's text: le réseau social chrétien, what one does there (faster and faster),
créé par un chrétien, pour les chrétiens. Then, in the silence after the sound, the RISE logo animation (the
app's own splash, made for a light background) with a heavy boom when its letters burst out, the slogan and
the App Store / Google Play badges.
Usage: python3 tools/build.py  -> index.html, compositions/fond.html, compositions/mots.html, shot-plan.json
(then python3 tools/boom.py, tools/music.py and tools/backdrop.py only if the sounds or the lights change)
"""
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
DURATION = 12.5  # the sound lasts 9.33 s; the logo plays out in the silence after it
# the reference's cuts, in seconds from its loop start, measured on the screen recording: each lands at
# the end of one of the sound's whooshes; the last one starts the end card
CUTS = [0.0, 0.714, 1.380, 2.000, 2.524, 3.024, 3.500, 3.952, 4.357, 4.714, 5.167, 5.524, 5.880, 6.214,
        6.547, 6.880, 7.190, 7.500, 7.785, 8.024, 8.334, 8.595, 8.880, 9.190]
W, H = 1080, 1920
FONT_FILE = ROOT / "assets" / "fonts" / "FreeSansBold.ttf"
TRACK = -0.035  # letter-spacing, em
S = 186  # every word's size
X_HEIGHT = 0.54  # FreeSans Bold's x-height, em
Y_C = 930  # where the middle of the x-height sits
LINE_W = 960  # the widest a line may be
GAP = 14  # between a word and the one landing under it
INK = {"sky": "#0b0b0c", "dusk": "#ffffff"}
FLAME = "#c2410c"  # the slogan's second word: the logo's flame, deep enough to read on the sky
EXIT_D = 0.1  # a word carried out on a whoosh leaves in the last 3 frames before the cut
PUNCH = 1.22  # a cut in closer: how much bigger the words come back

# the cards, in order: (words, how it comes in, how it leaves on the whoosh into the next cut[, how many cuts it
# stays for]). words: a word; (word, word under it, its size against the first) for two lines; None for the end
# card. The light flips on every card, but a word landing under another stays in its light, and the logo is on white.
CARDS = [
    # the statement, on the slowest cuts, each phrase built under its first words
    ("le réseau", "rise", None),  # letters rise from their baseline
    (("le réseau", "social", 1.8), "rise-under", "zoom"),  # "social" rises under it; the card flies at the camera
    ("créé par un", "slam", None),  # ...and the next words slam in from close up
    (("créé par un", "chrétien", 1.0), "rise-under", None),
    ("pour les", "track", None),  # letters close up from wide tracking
    (("pour les", "chrétiens.", 1.0), "rise-under", None),
    (("pour les", "chrétiens.", 1.0), "punch-in", "whip-left"),  # the same words, cut in closer: read for longer
    # what one does there: faster and faster
    ("partage", "whip-in-right", None),
    ("entraide", "track", None),
    ("prière", "pop", "push-up"),
    ("quiz", "push-in", None),
    ("verset", "drop", "whip-right"),
    ("groupes", "whip-in-left", None),
    ("messages", "focus", None),
    ("sondages", "rise", "zoom"),
    ("louange", "slam", None),
    ("témoignage", "track", None),
    ("communauté", "push-in", None),
    ("foi", "slam", None),
    ("espérance", "whip-in-right", None),
    ("amour", "pop", None),
    ("joie", "rise", None),
    ("paix", "focus", None),
    (None, "end", None),  # the silence: the logo and its boom, the slogan, the stores
]
# the end card: the logo animation (960x500, its logo 920 px wide at rest), the slogan, the badges.
# The animation starts 0.2 s in (its candle already up); its letters burst out 0.667 s in: the boom lands there.
SPLASH = dict(src="assets/brand/rise_splash_light.webm", w=960, h=500, scale=0.82, cx=480, cy=317, at=860)
SPLASH_FROM, BURST = 0.2, 0.667
BOOM_AT = round((round(CUTS[-1] * FPS) / FPS + BURST - SPLASH_FROM) * FPS) / FPS  # tools/music.py mixes the boom here
SLOGAN = (("Élève-toi.", 0.6), ("Ensemble.", 0.75))  # a word, the seconds after the boom
SLOGAN_SIZE, SLOGAN_BASE = 64, 1078
BADGES = (("assets/brand/badge_app_store_fr.png", "Télécharger dans l'App Store", 1.0),
          ("assets/brand/badge_google_play_fr.png", "Disponible sur Google Play", 1.1))
FLAME_AT = (365, 205)  # the flame, in the logo animation's own pixels: the warm light of the boom starts there
BADGE_W, BADGE_H, BADGE_GAP, BADGE_TOP = 400, 133, 26, 1142


def frame(t):
    return round(t * FPS) / FPS


def font(size):
    return ImageFont.truetype(str(FONT_FILE), size)


def pens(text, size, track=TRACK):
    """Each glyph's pen x from the word's start, kerned and tracked as the browser sets it."""
    f = font(size)
    return [f.getlength(text[: i + 1]) - f.getlength(ch) + i * track * size for i, ch in enumerate(text)]


def width(text, size, track=TRACK):
    return font(size).getlength(text) + track * size * (len(text) - 1)


def fit(text, size, w=LINE_W):
    return min(size, w / (width(text, 100) / 100))


def ink(text, size, left):
    """Per frame column, the word's ink: how high above its baseline and how low below it (px), or NaN."""
    f, pad = font(size), int(size)
    im = Image.new("L", (W + 2 * pad, int(3 * size) + 2 * pad), 0)
    d = ImageDraw.Draw(im)
    y0 = pad + int(1.5 * size)
    for ch, x in zip(text, pens(text, size)):
        d.text((pad + left + x, y0), ch, font=f, fill=255, anchor="ls")
    a = np.asarray(im)[:, pad: pad + W] > 100
    has = a.any(0)
    rows = np.arange(a.shape[0])[:, None]
    top = np.where(has, y0 - np.where(a, rows, 10 ** 6).min(0), np.nan)
    bottom = np.where(has, np.where(a, rows, -1).max(0) - y0, np.nan)
    return top, bottom


def tf(cx, cy, dx=0.0, dy=0.0, r=0.0, s=1.0):
    """A glyph's transform: moved by (dx, dy), turned by r degrees and scaled by s about (cx, cy). The same
    shape at rest and in motion, so GSAP interpolates it number by number."""
    return f"translate({cx:.1f} {cy:.1f}) translate({dx:.1f} {dy:.1f}) rotate({r:.1f}) scale({s:.3f}) translate({-cx:.1f} {-cy:.1f})"


class Line:
    """A word set on the frame: its glyphs, where each one sits, its baseline."""

    def __init__(self, text, size, base):
        self.text, self.size, self.base = text, size, base
        self.left = (W - width(text, size)) / 2
        f = font(size)
        self.glyphs = [(k, ch, self.left + x, self.left + x + f.getlength(ch) / 2)
                       for k, (ch, x) in enumerate(zip(text, pens(text, size))) if ch != " "]
        self.mid = base - X_HEIGHT * size / 2  # the middle of the x-height

    def svg(self, gid, light, clip=False):
        # each glyph in its own group, moved by an explicit transform about its own middle (no bbox needed)
        g = "".join(f'<g id="{gid}{k}" data-layout-allow-overlap transform="{tf(cx, self.mid)}">'
                    f'<text data-layout-allow-overlap x="{x:.1f}" y="{self.base:.1f}" style="font-size: {self.size:.1f}px; fill: {INK[light]}">'
                    f"{html.escape(ch)}</text></g>" for k, ch, x, cx in self.glyphs)
        if not clip:
            return f'<g id="{gid}">{g}</g>'
        # the baseline mask: letters rise from under it; room above for accents, below for descenders
        top, bottom = self.base - 1.0 * self.size, self.base + 0.27 * self.size
        return (f'<clipPath id="{gid}-clip"><rect x="0" y="{top:.0f}" width="{W}" height="{bottom - top:.0f}" /></clipPath>'
                f'<g id="{gid}" clip-path="url(#{gid}-clip)">{g}</g>')


def single(text):
    size = fit(text, S)
    return Line(text, size, Y_C + X_HEIGHT * size / 2)


def two_lines(first, under, k):
    """The first word where it sits alone; the one under it as close as their letters allow."""
    a = single(first)
    s2 = fit(under, a.size * k)
    _, below = ink(first, a.size, a.left)
    above, _ = ink(under, s2, (W - width(under, s2)) / 2)
    return a, Line(under, s2, a.base + np.nanmax(below + above) + GAP)


def cards():
    out, light, cut = [], "dusk", 0
    for i, (words, fx_in, fx_out, *rest) in enumerate(CARDS):
        span = rest[0] if rest else 1
        if fx_in == "end":  # the logo on plain white: it breaks from the sky and the dusk of the words
            light = "white"
        elif fx_in != "rise-under":  # a word landing under another stays in its light
            light = "sky" if light == "dusk" else "dusk"
        t1 = frame(CUTS[cut + span]) if cut + span < len(CUTS) else DURATION
        out.append(dict(id=f"c{i}", i=i, t0=frame(CUTS[cut]), t1=t1, words=words, fx_in=fx_in, fx_out=fx_out,
                        light=light, span=span))
        cut += span
    assert cut == len(CUTS), "the cards must cover every cut"
    return out


def lines(c):
    w = c["words"]
    if isinstance(w, tuple):
        return list(two_lines(*w))
    return [single(w)]


def card_html(c):
    cid, light, fx = c["id"], c["light"], c["fx_in"]
    if fx == "end":
        return f'<div id="{cid}" class="card"></div>'
    L = lines(c)
    mid = (L[0].mid + L[-1].mid) / 2
    style = f"transform-origin: {W / 2:.0f}px {mid:.0f}px; filter: url(#{cid}-f)"
    inner = L[0].svg(f"{cid}-a", light, fx == "rise")
    if len(L) > 1:
        inner += L[1].svg(f"{cid}-b", light, fx == "rise-under")
    return (f'<div id="{cid}" class="card" style="{style}" data-layout-allow-overflow>'
            f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{inner}</svg></div>')


def r3(t):
    return round(t, 3)


def motion(c):
    """The card's tweens: its entrance from its cut, its exit on the whoosh into the next one."""
    cid, t0, t1, fx, out = c["id"], c["t0"], c["t1"], c["fx_in"], c["fx_out"]
    if fx == "end":
        return []
    L = lines(c)
    d = r3(t1 - t0)
    dx = r3(d - (EXIT_D if out else 0))  # what the entrance may take before the exit
    card, blur = f'"#{cid}"', f'"#{cid}-blur"'
    js = [f'tl.set({card}, {{ visibility: "visible" }}, {t0});', f'tl.set({card}, {{ visibility: "hidden" }}, {t1});']

    def blur_in(sd, dur, ease="expo.out"):
        js.append(f'tl.fromTo({blur}, {{ attr: {{ stdDeviation: "{sd}" }} }}, {{ attr: {{ stdDeviation: "0 0" }}, duration: {dur}, ease: "{ease}" }}, {t0});')

    def settle(s0, ease="power2.out"):  # ends a frame before any exit takes the scale over
        js.append(f'tl.fromTo({card}, {{ scale: {s0} }}, {{ scale: 1, duration: {r3(dx - (1 / FPS if out else 0))}, ease: "{ease}" }}, {t0});')

    def glyph(gid, line, k, cx, start, dur, ease, at):
        """One glyph from a start (dx, dy, r, s) to rest."""
        js.append(f'tl.fromTo("#{gid}{k}", {{ attr: {{ transform: "{tf(cx, line.mid, *start)}" }} }}, '
                  f'{{ attr: {{ transform: "{tf(cx, line.mid)}" }}, duration: {dur}, ease: "{ease}" }}, {r3(at)});')

    def per_glyph(line, gid, start, dur, stagger, ease="expo.out"):
        n = len(line.glyphs)
        st = min(stagger, 0.12 / max(1, n - 1))
        for j, (k, _, x, cx) in enumerate(line.glyphs):
            glyph(gid, line, k, cx, start(j, cx), dur, ease, t0 + j * st)

    a = L[0]
    if fx == "rise":
        per_glyph(a, f"{cid}-a", lambda j, cx: (0, 1.3 * a.size, 0, 1), min(0.45, d), 0.03)
        settle(1.03)
    elif fx == "rise-under":  # the first word stays exactly where it was
        b = L[1]
        per_glyph(b, f"{cid}-b", lambda j, cx: (0, 1.3 * b.size, 0, 1), min(0.45, dx), 0.035)
        if c["span"] > 1:  # held over more than one whoosh: the camera moves in slowly while it is read
            js.append(f'tl.fromTo({card}, {{ scale: 1 }}, {{ scale: 1.05, duration: {dx}, ease: "sine.inOut" }}, {t0});')
    elif fx == "punch-in":  # the cut to a closer framing of the words already on screen, in the other light
        js.append(f'tl.fromTo({card}, {{ scale: {PUNCH * 1.1:.3f} }}, {{ scale: {PUNCH}, duration: {min(0.4, dx)}, ease: "expo.out" }}, {t0});')
        blur_in("10 10", 0.1, "power2.out")
    elif fx == "slam":
        js.append(f'tl.fromTo({card}, {{ scale: 1.6 }}, {{ scale: 1, duration: {min(0.36, dx)}, ease: "power4.out" }}, {t0});')
        blur_in("14 14", 0.12, "power2.out")
    elif fx in ("whip-in-right", "whip-in-left"):
        sign = 1 if fx == "whip-in-right" else -1
        js.append(f'tl.fromTo({card}, {{ x: {sign * 620} }}, {{ x: 0, duration: {min(0.32, dx)}, ease: "expo.out" }}, {t0});')
        blur_in("46 0", 0.16)
        if len(L) > 1:  # the second line trails a little: parallax
            js.append(f'tl.fromTo("#{cid}-b", {{ x: {sign * 160} }}, {{ x: 0, duration: {min(0.38, dx)}, ease: "expo.out" }}, {t0});')
    elif fx == "push-in":
        js.append(f'tl.fromTo({card}, {{ y: 560 }}, {{ y: 0, duration: {min(0.32, dx)}, ease: "expo.out" }}, {t0});')
        blur_in("0 40", 0.16)
    elif fx == "pop":
        per_glyph(a, f"{cid}-a", lambda j, cx: (0, 0, 0, 0), min(0.34, d), 0.03, "back.out(1.6)")
        settle(1.03)
    elif fx == "drop":
        per_glyph(a, f"{cid}-a", lambda j, cx: (0, -1.15 * a.size, 12 if j % 2 else -12, 1), min(0.36, dx), 0.028, "power4.out")
    elif fx == "track":  # every letter starts as far again from the middle, and closes up
        xc = W / 2
        js.append(f'tl.fromTo({card}, {{ scale: 1.08 }}, {{ scale: 1, duration: {dx}, ease: "expo.out" }}, {t0});')
        for k, _, x, cx in a.glyphs:
            glyph(f"{cid}-a", a, k, cx, (0.9 * (cx - xc), 0, 0, 1), min(0.45, dx), "expo.out", t0)
        blur_in("12 0", 0.22)
    elif fx == "focus":
        js.append(f'tl.fromTo({card}, {{ scale: 1.16 }}, {{ scale: 1, duration: {dx}, ease: "power2.out" }}, {t0});')
        blur_in("18 18", 0.12, "power1.in")

    if out:  # carried out on the whoosh, the way the next word comes in
        x0 = r3(t1 - EXIT_D)
        move, sd = {"zoom": ("scale: 2.4", "16 16"), "whip-left": ("x: -620", "46 0"), "whip-right": ("x: 620", "46 0"),
                    "push-up": ("y: -560", "0 40")}[out]
        js.append(f'tl.to({card}, {{ {move}, duration: {EXIT_D}, ease: "power2.in" }}, {x0});')
        js.append(f'tl.to({blur}, {{ attr: {{ stdDeviation: "{sd}" }}, duration: {EXIT_D}, ease: "power2.in" }}, {x0});')
    return ["        " + s for s in js]


def fond(C):
    flips = "\n".join(f'        tl.set("#{layer}", {{ visibility: "{"visible" if c["light"] == layer else "hidden"}" }}, {c["t0"]});'
                      for c in C for layer in ("dusk", "white"))
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    <template>
      <style>
        #root {{ position: absolute; inset: 0; overflow: hidden; background: #bfe3f6; }}
        .light {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
        #dusk, #white {{ visibility: hidden; }}
        #white {{ background: #ffffff; }}
      </style>
      <div id="root" data-composition-id="fond" data-width="{W}" data-height="{H}">
        <img id="sky" class="light" src="assets/sky.png" alt="" data-layout-allow-overflow />
        <img id="dusk" class="light" src="assets/dusk.png" alt="" data-layout-allow-overflow />
        <div id="white" class="light"></div>
      </div>
      <script>
        window.__timelines = window.__timelines || {{}};
        const tl = gsap.timeline({{ paused: true }});
        // both lights drift in together, so a cut changes the light, not the place
        tl.fromTo(".light", {{ scale: 1 }}, {{ scale: 1.05, duration: {DURATION}, ease: "none" }}, 0);
        // the sky (black words) and dusk (white words), flipped on every card; plain white for the logo
{flips}
        window.__timelines["fond"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def mots(C):
    filters = "".join(f'<filter id="{c["id"]}-f" x="-15%" y="-8%" width="130%" height="116%">'
                      f'<feGaussianBlur id="{c["id"]}-blur" stdDeviation="0 0" /></filter>' for c in C if c["fx_in"] != "end")
    cards_html = "\n        ".join(card_html(c) for c in C)
    script = "\n".join(s for c in C for s in motion(c))
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    <template>
      <style>
        @font-face {{ font-family: "Rise Sans"; font-weight: 700; src: url("assets/fonts/FreeSansBold.ttf") format("truetype"); }}
        #root {{ position: absolute; inset: 0; }}
        .card {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; visibility: hidden; }}
        .card svg {{ position: absolute; left: 0; top: 0; overflow: visible; }}
        text {{ font-family: "Rise Sans", sans-serif; font-weight: 700; }}
        text.word {{ letter-spacing: {TRACK}em; }}
      </style>
      <div id="root" data-composition-id="mots" data-width="{W}" data-height="{H}">
        <svg width="0" height="0" style="position: absolute">{filters}</svg>
        {cards_html}
      </div>
      <script>
        window.__timelines = window.__timelines || {{}};
        const tl = gsap.timeline({{ paused: true }});
{script}
        window.__timelines["mots"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def end_card(t0):
    """The logo animation and its boom, the slogan under it, the two store badges: HTML, CSS and tweens."""
    sw, sh, k = SPLASH["w"], SPLASH["h"], SPLASH["scale"]
    left, top = W / 2 - SPLASH["cx"] * k, SPLASH["at"] - SPLASH["cy"] * k
    dur = r3(DURATION - t0)
    line = Line(" ".join(t for t, _ in SLOGAN), SLOGAN_SIZE, SLOGAN_BASE)
    words, start = [], 0
    for j, (word, _) in enumerate(SLOGAN):  # each word of the slogan rises from its own baseline mask
        glyphs = [g for g in line.glyphs if start <= g[0] < start + len(word)]
        start += len(word) + 1
        fill = FLAME if j else INK["sky"]
        words.append("".join(f'<text data-layout-allow-overlap x="{x:.1f}" y="{line.base:.1f}" style="font-size: {SLOGAN_SIZE}px; fill: {fill}">{html.escape(ch)}</text>'
                             for _, ch, x, _ in glyphs))
    top_m, bot_m = line.base - 1.05 * SLOGAN_SIZE, line.base + 0.3 * SLOGAN_SIZE
    slogan = (f'<svg id="slogan" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><clipPath id="slogan-clip">'
              f'<rect x="0" y="{top_m:.0f}" width="{W}" height="{bot_m - top_m:.0f}" /></clipPath><g clip-path="url(#slogan-clip)">'
              + "".join(f'<g id="slogan{j}">{w}</g>' for j, w in enumerate(words)) + "</g></svg>")
    bx = (W - 2 * BADGE_W - BADGE_GAP) / 2
    badges = "".join(f'<img id="badge{j}" class="badge" src="{src}" alt="{html.escape(alt)}" '
                     f'style="left: {bx + j * (BADGE_W + BADGE_GAP):.0f}px; top: {BADGE_TOP}px" />' for j, (src, alt, _) in enumerate(BADGES))
    body = f"""      <div id="fin" data-layout-allow-overflow>
        <div id="flash"></div>
        <div id="splashw"><video id="splash" class="clip" src="{SPLASH["src"]}" muted playsinline data-start="{t0}" data-duration="{dur}" data-media-start="{SPLASH_FROM}" data-track-index="5"></video></div>
        {slogan}
        {badges}
      </div>"""
    fx, fy = left + FLAME_AT[0] * k, top + FLAME_AT[1] * k
    css = f"""      #fin {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #flash {{ position: absolute; left: {fx - 520:.0f}px; top: {fy - 520:.0f}px; width: 1040px; height: 1040px; visibility: hidden;
        background: radial-gradient(closest-side, rgba(255, 168, 60, 0.6), rgba(255, 200, 120, 0.25) 45%, rgba(255, 255, 255, 0)); }}
      #splashw {{ position: absolute; left: {left:.0f}px; top: {top:.0f}px; width: {sw * k:.0f}px; height: {sh * k:.0f}px; transform-origin: {SPLASH["cx"] * k:.0f}px {SPLASH["cy"] * k:.0f}px; }}
      #splash {{ position: absolute; left: 0; top: 0; width: {sw * k:.0f}px; height: {sh * k:.0f}px; display: block; }}
      #slogan {{ position: absolute; left: 0; top: 0; overflow: visible; }}
      #slogan text {{ font-family: "Rise Sans", sans-serif; font-weight: 700; }}
      .badge {{ position: absolute; width: {BADGE_W}px; height: {BADGE_H}px; display: block; opacity: 0; }}"""
    js = [f'tl.fromTo("#splashw", {{ scale: 0.96 }}, {{ scale: 1.03, duration: {dur}, ease: "sine.out" }}, {t0});']
    # the boom: a warm light spreads from the flame over the white as the letters burst out
    b = BOOM_AT
    js.append(f'tl.set("#flash", {{ visibility: "visible" }}, {b});')
    js.append(f'tl.fromTo("#flash", {{ opacity: 1, scale: 0.35 }}, {{ opacity: 0, scale: 1.6, duration: 1.0, ease: "power2.out" }}, {b});')
    js.append(f'tl.set("#flash", {{ visibility: "hidden" }}, {r3(b + 1.0)});')
    for j, (_, at) in enumerate(SLOGAN):
        js.append(f'tl.fromTo("#slogan{j}", {{ y: {1.4 * SLOGAN_SIZE:.0f} }}, {{ y: 0, duration: 0.5, ease: "expo.out" }}, {r3(b + at)});')
    for j, (_, _, at) in enumerate(BADGES):
        js.append(f'tl.fromTo("#badge{j}", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "expo.out" }}, {r3(b + at)});')
    return body, css, "\n".join("      " + s for s in js)


def root(C):
    body, css, js = end_card(C[-1]["t0"])
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Rise Sans"; font-weight: 700; src: url("assets/fonts/FreeSansBold.ttf") format("truetype"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #bfe3f6; }}
      #stage {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
{css}
    </style>
  </head>
  <body>
    <div id="stage" data-composition-id="main" data-start="0" data-duration="{DURATION}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
      <div id="fond" class="clip" data-composition-id="fond" data-composition-src="compositions/fond.html" data-start="0" data-duration="{DURATION}"
        data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <div id="mots" class="clip" data-composition-id="mots" data-composition-src="compositions/mots.html" data-start="0" data-duration="{DURATION}"
        data-track-index="2" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
{body}
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{DURATION}" data-track-index="3" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
{js}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def shot_plan(C):
    def text(c):
        w = c["words"]
        return " / ".join(w[:2]) if isinstance(w, tuple) else (w or "RISE logo animation · Élève-toi. Ensemble. · store badges")
    return {
        "category": "kinetic-type",
        "duration_s": DURATION,
        "fps": FPS,
        "canvas": {"w": W, "h": H, "aspect": "9:16"},
        "style": "the reference reel's edit, cut for cut on its own sound, every word moved on the whooshes: letters rising from "
                 "their baseline, popping, dropping, closing up from wide tracking; words slamming in, whipping or pushing "
                 "in with motion blur, pulled into focus, cut in closer; whooshes carried across cuts (zoom, whip, push); the "
                 "light flips between the RISE sky (black words) and dusk grey-blue (white words); then, in the silence, the "
                 "app's logo animation on white with a heavy boom, the slogan and the store badges",
        "palette": ["#93cdef", "#bfe3f6", "#def1fb", "#d0d1d7", "#95a0e0", "#717480", INK["sky"], INK["dusk"], FLAME],
        "font": "FreeSans Bold (GNU FreeFont, GPL with font exception), letter-spacing -0.035em",
        "beats": [frame(t) for t in CUTS],
        "export": "mp4",
        "asset_needs": [],
        "block": "caption-kinetic-slam",
        "customize": {"note": "its one-word-per-beat structure, rebuilt by tools/build.py on the reference's own cut times"},
        "content": {"scenes": [{"id": c["id"], "start": c["t0"], "end": c["t1"], "text": text(c), "motion": c["fx_in"],
                                "exit": c["fx_out"], "light": c["light"]} for c in C]},
    }


def main():
    C = cards()
    (ROOT / "compositions").mkdir(exist_ok=True)
    (ROOT / "compositions" / "fond.html").write_text(fond(C))
    (ROOT / "compositions" / "mots.html").write_text(mots(C))
    (ROOT / "index.html").write_text(root(C))
    (ROOT / "shot-plan.json").write_text(json.dumps(shot_plan(C), ensure_ascii=False, indent=1) + "\n")
    for c in C:
        print(f"{c['t0']:6.3f}-{c['t1']:6.3f}  {c['light']:4s}  {c['fx_in']:13s} {str(c['fx_out'] or ''):10s} {c['words']}")
    print(f"{DURATION}s")


if __name__ == "__main__":
    main()
