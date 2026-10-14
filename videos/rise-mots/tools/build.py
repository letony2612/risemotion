"""The reel « rise. » — RISE in a few words, one card at a time, cut on the music's eighth notes.

The grammar is the reference reel's (the "graphics / transitions / ideas / feelings / re / repe. / repea /
repeat." reel the user sent): a Helvetica-style bold (FreeSans Bold), lowercase, tracked tight, every word
the same size; a hard cut on every eighth note that flips the light between the RISE sky (black words) and
dusk (white words); a word lands a little big and settles, some with a focus pull or a horizontal smear on
their first frames; "rise" typed letter by letter, then blown up to the edges and eaten by blobs, then an
empty beat; a word that stays while the next one lands under it. It ends on the logo, on the track's final hit.
Usage: python3 tools/build.py  -> index.html, compositions/fond.html, compositions/mots.html, shot-plan.json
(then python3 tools/music.py and tools/backdrop.py only if the music or the lights change)
"""
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
EIGHTH = 60 / 105 / 2  # the music's eighth note (tools/music.py)
LEAD = 0.010  # the beats' attacks sit this far into assets/music.wav
DURATION = 10.3
W, H = 1080, 1920
FONT_FILE = ROOT / "assets" / "fonts" / "FreeSansBold.ttf"
TRACK = -0.035  # letter-spacing, em
S = 186  # every word's size
X_HEIGHT = 0.54  # FreeSans Bold's x-height, em
Y_C = 930  # where the middle of the x-height sits
EDGE_W = 1030  # a word blown up to the edges
UNDER_W = 960  # the widest a word landing under another may be
GAP = 14  # between a word and the one landing under it
INK = {"sky": "#0b0b0c", "dusk": "#ffffff"}
FLAME = "#c2410c"  # the slogan's second word: the logo's flame, deep enough to read on the sky

# (eighth note, words, motion). words: a word; (word, word landing under it, its size against the first)
# for a pair; None for the empty beat; "logo" for the end. The light flips on every card but the empty beat.
CARDS = [
    (0, "r", "settle"),
    (1, "ri.", "type"),
    (2, "ris", "type"),
    (3, "rise.", "type"),
    (4, "rise.", "eaten"),  # the break's hit: blown up to the edges, eaten by blobs in the silence after it
    (5, None, "empty"),
    (6, "le réseau", "focus"),  # on the riser
    (9, ("le réseau", "social", 1.8), "pair"),
    (12, "chrétien.", "smear"),  # the drop
    (14, "partage", "settle"),
    (15, "entraide", "smear"),
    (16, "prière", "settle"),
    (17, "quiz", "settle"),
    (18, "verset", "focus"),
    (20, "créé", "smear"),
    (22, "par un", "settle"),
    (23, "chrétien", "settle"),
    (24, "pour les", "settle"),
    (26, ("pour les", "chrétiens.", 1.0), "pair"),
    (28, "logo", "logo"),  # the track's final hit
]
SLOGAN = (("Élève-toi.", 30), (" Ensemble.", 32))  # under the logo, a word on each of these eighth notes
SLOGAN_SIZE = 70
SLOGAN_TRACK = -0.02
LOGO_W = 640
# the blobs that eat the blown-up word: centre, last radius, the frame they start on (after the erase starts)
BLOBS = [(600, 930, 270, 0), (470, 860, 210, 0), (760, 1000, 230, 1), (330, 990, 200, 1),
         (880, 850, 190, 2), (200, 860, 160, 2), (300, 720, 130, 2), (965, 1010, 130, 3)]


def frame(t):
    return round(t * FPS) / FPS


def at(eighth):
    return frame(LEAD + eighth * EIGHTH)


def font(size):
    return ImageFont.truetype(str(FONT_FILE), size)


def pens(text, size, track=TRACK):
    """Each glyph's pen x from the word's start, kerned and tracked as the browser sets it."""
    f = font(size)
    return [f.getlength(text[: i + 1]) - f.getlength(ch) + i * track * size for i, ch in enumerate(text)]


def width(text, size, track=TRACK):
    return font(size).getlength(text) + track * size * (len(text) - 1)


def ink(text, size, left, base):
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


def word(text, size, base, light, cls=""):
    left = (W - width(text, size)) / 2
    return left, (f'<text class="{cls}" x="{left:.1f}" y="{base:.1f}" style="font-size: {size:.1f}px; fill: {INK[light]}">'
                  f"{html.escape(text)}</text>")


def cards():
    out = []
    for i, (k, words, fx) in enumerate(CARDS):
        t0 = at(k)
        t1 = at(CARDS[i + 1][0]) if i + 1 < len(CARDS) else DURATION
        out.append(dict(id=f"c{k}", k=k, t0=t0, t1=t1, words=words, fx=fx))
    light = "dusk"
    for c in out:
        if c["fx"] != "empty":
            light = "sky" if light == "dusk" else "dusk"
        c["light"] = light
    return out


def svg(inner, defs=""):
    return (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            + (f"<defs>{defs}</defs>" if defs else "") + inner + "</svg>")


def layer(lid, inner, origin):
    return f'<div id="{lid}" class="layer" style="transform-origin: {origin[0]:.0f}px {origin[1]:.0f}px">{inner}</div>'


def card_html(c):
    """The card's HTML, and the transform origins of its layers (a: the word, b: the word under it)."""
    cid, words, fx, light = c["id"], c["words"], c["fx"], c["light"]
    base = Y_C + X_HEIGHT * S / 2
    if fx == "empty":
        return f'<div id="{cid}" class="card"></div>', {}
    if fx == "logo":
        lh = LOGO_W * 264 / 767
        top = Y_C - 40 - lh / 2
        line = "".join(t for t, _ in SLOGAN)
        x = (W - width(line, SLOGAN_SIZE, SLOGAN_TRACK)) / 2
        sb = Y_C + 210
        spans = "".join(f'<tspan id="{cid}-s{j}" style="visibility: hidden{"; fill: " + FLAME if j else ""}">{html.escape(t)}</tspan>'
                        for j, (t, _) in enumerate(SLOGAN))
        slogan = (f'<text x="{x:.1f}" y="{sb:.1f}" style="font-size: {SLOGAN_SIZE}px; letter-spacing: {SLOGAN_TRACK}em; '
                  f'white-space: pre; fill: {INK[light]}">{spans}</text>')
        a = layer(f"{cid}-a", f'<img class="logo" src="assets/rise_logo.png" alt="RISE" style="left: {(W - LOGO_W) / 2:.0f}px; '
                              f'top: {top:.0f}px; width: {LOGO_W}px" />', (W / 2, Y_C - 40))
        b = layer(f"{cid}-b", svg(slogan), (W / 2, sb))
        return f'<div id="{cid}" class="card" data-layout-allow-overflow>{a}{b}</div>', {"a": (W / 2, Y_C - 40)}
    if fx == "eaten":
        size = EDGE_W / (width(words, 100) / 100)
        b = Y_C + X_HEIGHT * size / 2
        circles = "".join(f'<circle id="{cid}-blob{j}" cx="{x}" cy="{y}" r="0" fill="#000" />' for j, (x, y, _, _) in enumerate(BLOBS))
        defs = (f'<filter id="{cid}-feather" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10" /></filter>'
                f'<mask id="{cid}-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
                f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff" /><g filter="url(#{cid}-feather)">{circles}</g></mask>')
        _, t = word(words, size, b, light)
        t = t.replace("<text ", f'<text mask="url(#{cid}-mask)" ', 1)
        return f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(t, defs), (W / 2, Y_C))}</div>', {}
    if isinstance(words, tuple):
        first, under, k = words
        size = min(S * k, UNDER_W / (width(under, 100) / 100))
        fl, ft = word(first, S, base, light)
        ul = (W - width(under, size)) / 2
        _, fb = ink(first, S, fl, base)
        ut, _ = ink(under, size, ul, 0)
        sep = np.nanmax(fb + ut) + GAP  # as close under the first word as their letters allow
        ub = base + sep
        _, utext = word(under, size, ub, light)
        origin = (W / 2, ub - 0.73 * size)  # its top: it settles down and out, never into the word above
        html_ = (f'<div id="{c["id"]}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(ft), (W / 2, Y_C))}'
                 f'{layer(cid + "-b", svg(utext), origin)}</div>')
        return html_, {"a": (W / 2, Y_C), "b": origin}
    _, t = word(words, S, base, light)
    return f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(t), (W / 2, Y_C))}</div>', {"a": (W / 2, Y_C)}


def motion(c):
    cid, t0, t1, fx = c["id"], c["t0"], c["t1"], c["fx"]
    d = round(t1 - t0, 3)
    js = [f'tl.set("#{cid}", {{ visibility: "visible" }}, {t0});']
    if fx != "logo":
        js.append(f'tl.set("#{cid}", {{ visibility: "hidden" }}, {t1});')
    a, b = f'"#{cid}-a"', f'"#{cid}-b"'
    if fx == "settle":  # lands a little big and settles for as long as it stays
        js.append(f'tl.fromTo({a}, {{ scale: 1.07 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
    elif fx == "focus":  # a focus pull: out of focus for three frames, then sharp, still settling
        js.append(f'tl.fromTo({a}, {{ scale: 1.14 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
        js.append(f'tl.fromTo({a}, {{ filter: "blur(16px)" }}, {{ filter: "blur(0px)", duration: 0.1, ease: "power1.in", immediateRender: false }}, {t0});')
    elif fx == "smear":  # a horizontal smear on its first two frames
        js.append(f'tl.fromTo({a}, {{ scale: 1.12 }}, {{ scale: 1, duration: {d}, ease: "power3.out" }}, {t0});')
        js.append(f'tl.fromTo("#{cid}-smear", {{ attr: {{ stdDeviation: "18 0" }} }}, '
                  f'{{ attr: {{ stdDeviation: "0 0" }}, duration: 0.067, ease: "power1.in" }}, {t0});')
    elif fx == "pair":  # the first word stays where it was; the one under it lands and settles
        js.append(f'tl.fromTo({b}, {{ scale: 1.07 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
    elif fx == "eaten":  # held for three frames, then the blobs eat it; what is left goes with the cut
        e0 = t0 + 3 / FPS
        for j, (_, _, r, f0) in enumerate(BLOBS):
            js.append(f'tl.fromTo("#{cid}-blob{j}", {{ attr: {{ r: 0 }} }}, '
                      f'{{ attr: {{ r: {r} }}, duration: 0.1, ease: "power1.out" }}, {round(e0 + f0 / FPS, 3)});')
    elif fx == "logo":
        js.append(f'tl.fromTo({a}, {{ scale: 1.1 }}, {{ scale: 1, duration: 1.2, ease: "power3.out" }}, {t0});')
        js.append(f'tl.fromTo("#{cid}-smear", {{ attr: {{ stdDeviation: "18 0" }} }}, '
                  f'{{ attr: {{ stdDeviation: "0 0" }}, duration: 0.067, ease: "power1.in" }}, {t0});')
        for j, (_, k) in enumerate(SLOGAN):
            js.append(f'tl.set("#{cid}-s{j}", {{ visibility: "visible" }}, {at(k)});')
    return ["        " + s for s in js]


def fond(C):
    flips = "\n".join(f'        tl.set("#dusk", {{ visibility: "{"visible" if c["light"] == "dusk" else "hidden"}" }}, {c["t0"]});' for c in C)
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
        #dusk {{ visibility: hidden; }}
      </style>
      <div id="root" data-composition-id="fond" data-width="{W}" data-height="{H}">
        <img id="sky" class="light" src="assets/sky.png" alt="" data-layout-allow-overflow />
        <img id="dusk" class="light" src="assets/dusk.png" alt="" data-layout-allow-overflow />
      </div>
      <script>
        window.__timelines = window.__timelines || {{}};
        const tl = gsap.timeline({{ paused: true }});
        // both lights drift in together, so a cut changes the light, not the place
        tl.fromTo(".light", {{ scale: 1 }}, {{ scale: 1.04, duration: {DURATION}, ease: "none" }}, 0);
        // the sky (black words) and dusk (white words), flipped on every card
{flips}
        window.__timelines["fond"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def mots(C):
    parts, js, filters = [], [], []
    for c in C:
        h, _ = card_html(c)
        parts.append(h)
        js += motion(c)
        if c["fx"] in ("smear", "logo"):
            filters.append(f'<filter id="{c["id"]}-smear-f" x="-30%" y="-10%" width="160%" height="120%">'
                           f'<feGaussianBlur id="{c["id"]}-smear" stdDeviation="0 0" /></filter>')
    rules = "\n".join(f'        #{c["id"]}-a {{ filter: url(#{c["id"]}-smear-f); }}' for c in C if c["fx"] in ("smear", "logo"))
    cards_html = "\n        ".join(parts)
    script = "\n".join(js)
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
        .layer {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
        .layer svg {{ position: absolute; left: 0; top: 0; overflow: visible; }}
        text {{ font-family: "Rise Sans", sans-serif; font-weight: 700; letter-spacing: {TRACK}em; }}
        .logo {{ position: absolute; height: auto; }}
{rules}
      </style>
      <div id="root" data-composition-id="mots" data-width="{W}" data-height="{H}">
        <svg width="0" height="0" style="position: absolute">{"".join(filters)}</svg>
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


def root():
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #bfe3f6; }}
      #stage {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
    </style>
  </head>
  <body>
    <div id="stage" data-composition-id="main" data-start="0" data-duration="{DURATION}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
      <div id="fond" class="clip" data-composition-id="fond" data-composition-src="compositions/fond.html" data-start="0" data-duration="{DURATION}"
        data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <div id="mots" class="clip" data-composition-id="mots" data-composition-src="compositions/mots.html" data-start="0" data-duration="{DURATION}"
        data-track-index="2" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{DURATION}" data-track-index="3" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def shot_plan(C):
    def text(c):
        w = c["words"]
        return " / ".join(w[:2]) if isinstance(w, tuple) else ("RISE · " + "".join(t for t, _ in SLOGAN) if w == "logo" else (w or ""))
    return {
        "category": "kinetic-type",
        "duration_s": DURATION,
        "fps": FPS,
        "canvas": {"w": W, "h": H, "aspect": "9:16"},
        "style": "the reference reel's grammar: one lowercase word at a time in a Helvetica-style bold tracked tight, all the same "
                 "size; a hard cut on every eighth note that flips the light between the RISE sky (black words) and dusk grey-blue "
                 "(white words); words land a little big and settle, some with a focus pull or a horizontal smear; rise typed, "
                 "blown up to the edges and eaten by blobs, an empty beat; a word landing under the one that stays; logo on the final hit",
        "palette": ["#93cdef", "#bfe3f6", "#def1fb", "#d0d1d7", "#95a0e0", "#717480", INK["sky"], INK["dusk"], FLAME],
        "font": "FreeSans Bold (GNU FreeFont, GPL with font exception), letter-spacing -0.035em",
        "beats": [round(LEAD + k * EIGHTH, 3) for k in range(int((DURATION - LEAD) / EIGHTH) + 1)],
        "export": "mp4",
        "asset_needs": [],
        "block": "caption-kinetic-slam",
        "customize": {"note": "its one-word-per-beat structure, rebuilt by tools/build.py on the music's eighth notes"},
        "content": {"scenes": [{"id": c["id"], "start": c["t0"], "end": c["t1"], "text": text(c), "motion": c["fx"],
                                "light": c["light"]} for c in C]},
    }


def main():
    C = cards()
    (ROOT / "compositions").mkdir(exist_ok=True)
    (ROOT / "compositions" / "fond.html").write_text(fond(C))
    (ROOT / "compositions" / "mots.html").write_text(mots(C))
    (ROOT / "index.html").write_text(root())
    (ROOT / "shot-plan.json").write_text(json.dumps(shot_plan(C), ensure_ascii=False, indent=1) + "\n")
    for c in C:
        print(f"{c['t0']:6.3f}-{c['t1']:6.3f}  {c['light']:4s}  {c['fx']:6s} {c['words']}")
    print(f"{DURATION}s")


if __name__ == "__main__":
    main()
