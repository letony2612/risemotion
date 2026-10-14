"""The reel « rise. » — RISE in a few words, one card at a time, cut on the reference reel's own sound.

The user sent the reference reel ("graphics / transitions / ideas / feelings / re / repe. / repea / repeat.")
and then its audio: a run of whooshes that speed up. This reel takes the reference's edit as it is, measured
on the screen recording frame by frame: the same 24 cuts at the same times (each at the end of a whoosh) and
the same moves, with RISE's words in place of the reference's.
- a Helvetica-style bold (FreeSans Bold), lowercase, tracked tight, every word the same size;
- every cut flips the light between the RISE sky (black words) and dusk (white words);
- a word lands a little big and settles; some come in out of focus, some with a horizontal smear;
- the statement first, where a word stays while the next one lands under it;
- then the list, faster and faster; then "r / ri. / ris / rise." typed; then the logo blown up to the edges
  and eaten by blobs on the last whoosh; then an empty, silent beat, and the loop starts again.
Usage: python3 tools/build.py  -> index.html, compositions/fond.html, compositions/mots.html, shot-plan.json
(then python3 tools/music.py and tools/backdrop.py only if the sound or the lights change)
"""
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
LOOP = 9.5  # the reference loops every 9.5 s; its sound lasts 9.33 s
# the reference's cuts, in seconds from its loop start, measured on the screen recording: each lands at
# the end of one of the sound's whooshes
CUTS = [0.0, 0.714, 1.380, 2.000, 2.524, 3.024, 3.500, 3.952, 4.357, 4.714, 5.167, 5.524, 5.880, 6.214,
        6.547, 6.880, 7.190, 7.500, 7.785, 8.024, 8.334, 8.595, 8.880, 9.190]
W, H = 1080, 1920
FONT_FILE = ROOT / "assets" / "fonts" / "FreeSansBold.ttf"
TRACK = -0.035  # letter-spacing, em
S = 186  # every word's size
X_HEIGHT = 0.54  # FreeSans Bold's x-height, em
Y_C = 930  # where the middle of the x-height sits
EDGE_W = 1030  # the logo blown up to the edges
LINE_W = 960  # the widest a line may be
GAP = 14  # between a word and the one landing under it
INK = {"sky": "#0b0b0c", "dusk": "#ffffff"}
LOGO = (767, 264, 155)  # rise_logo.png: width, height, the middle of its letters

# one card per cut, in order: (words, move). words: a word; (word, word under it, its size against the
# first) for two lines; "logo"; None for the empty beat. The light flips on every card but the empty beat.
CARDS = [
    ("le réseau", "focus"),  # the loop opens out of focus, like the reference's "we"
    (("le réseau", "social", 1.8), "pair"),  # "le réseau" stays, "social" lands under it
    ("chrétien.", "settle"),
    (("créé par un", "chrétien", 1.0), "stack"),
    ("pour les", "settle"),
    (("pour les", "chrétiens.", 1.0), "pair-smear"),
    ("partage", "settle"),  # the list: faster and faster
    ("entraide", "settle"),
    ("prière", "settle"),
    ("quiz", "settle"),
    ("verset", "settle"),
    ("groupes", "settle"),
    ("louange", "smear"),
    ("témoignage", "settle"),
    ("foi", "settle"),
    ("amour", "smear"),
    ("joie", "smear"),
    ("paix", "focus"),
    ("r", "settle"),  # typed
    ("ri.", "type"),
    ("ris", "type"),
    ("rise.", "type"),
    ("logo", "eaten"),  # blown up to the edges, eaten on the last whoosh
    (None, "empty"),  # silent; then the loop
]
# the blobs that eat the logo: centre in the frame, last radius, the frame they start on after the erase starts
BLOBS = [(560, 930, 280, 0), (420, 870, 220, 0), (740, 1000, 240, 1), (300, 990, 200, 1),
         (880, 870, 200, 2), (180, 860, 170, 2), (400, 760, 140, 2), (990, 1010, 140, 3)]
FEATHER = 12  # half the soft edge of a blob, px
ERASE_AFTER = 5  # frames the logo holds before the blobs start


def frame(t):
    return round(t * FPS) / FPS


def font(size):
    return ImageFont.truetype(str(FONT_FILE), size)


def pens(text, size):
    """Each glyph's pen x from the word's start, kerned and tracked as the browser sets it."""
    f = font(size)
    return [f.getlength(text[: i + 1]) - f.getlength(ch) + i * TRACK * size for i, ch in enumerate(text)]


def width(text, size):
    return font(size).getlength(text) + TRACK * size * (len(text) - 1)


def fit(text, size):
    return min(size, LINE_W / (width(text, 100) / 100))


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


def text_el(text, size, base, light):
    left = (W - width(text, size)) / 2
    return (f'<text x="{left:.1f}" y="{base:.1f}" style="font-size: {size:.1f}px; fill: {INK[light]}">'
            f"{html.escape(text)}</text>")


def two_lines(first, under, k):
    """The first word where it sits alone; the one under it as close as their letters allow."""
    s1 = fit(first, S)
    s2 = fit(under, s1 * k)
    b1 = Y_C + X_HEIGHT * s1 / 2
    _, below = ink(first, s1, (W - width(first, s1)) / 2)
    above, _ = ink(under, s2, (W - width(under, s2)) / 2)
    b2 = b1 + np.nanmax(below + above) + GAP
    return (first, s1, b1), (under, s2, b2)


def cards():
    out, light = [], "dusk"
    for i, (words, fx) in enumerate(CARDS):
        if fx != "empty":
            light = "sky" if light == "dusk" else "dusk"
        t1 = frame(CUTS[i + 1]) if i + 1 < len(CUTS) else LOOP
        out.append(dict(id=f"c{i}", i=i, t0=frame(CUTS[i]), t1=t1, words=words, fx=fx, light=light))
    return out


def svg(inner):
    return f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{inner}</svg>'


def layer(lid, inner, origin):
    return f'<div id="{lid}" class="layer" style="transform-origin: {origin[0]:.0f}px {origin[1]:.0f}px">{inner}</div>'


def logo_box():
    w0, h0, mid = LOGO
    k = EDGE_W / w0
    return (W - EDGE_W) / 2, Y_C - mid * k, EDGE_W, h0 * k


def card_html(c):
    cid, words, fx, light = c["id"], c["words"], c["fx"], c["light"]
    if fx == "empty":
        return f'<div id="{cid}" class="card"></div>'
    if fx == "eaten":
        left, top, w, _ = logo_box()
        masks = ", ".join(f"radial-gradient(circle at {x - left:.0f}px {y - top:.0f}px, transparent calc(var(--b{j}) - {FEATHER}px), "
                          f"#000 calc(var(--b{j}) + {FEATHER}px))" for j, (x, y, _, _) in enumerate(BLOBS))
        start = "; ".join(f"--b{j}: {-2 * FEATHER}px" for j in range(len(BLOBS)))
        img = (f'<img id="{cid}-logo" class="logo" src="assets/rise_logo.png" alt="RISE" style="left: {left:.0f}px; top: {top:.0f}px; '
               f"width: {w:.0f}px; {start}; -webkit-mask-image: {masks}; mask-image: {masks}; -webkit-mask-repeat: no-repeat; "
               f'mask-repeat: no-repeat; -webkit-mask-composite: source-in; mask-composite: intersect" />')
        return f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", img, (W / 2, Y_C))}</div>'
    if isinstance(words, tuple):
        (t1, s1, b1), (t2, s2, b2) = two_lines(*words)
        a, b = text_el(t1, s1, b1, light), text_el(t2, s2, b2, light)
        if fx == "stack":  # both lines are new: they land together
            mid = (b1 - X_HEIGHT * s1 + b2) / 2
            return f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(a + b), (W / 2, mid))}</div>'
        # the first word stays where it was; the one under it settles from its top, never into the first
        return (f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(a), (W / 2, Y_C))}'
                f'{layer(cid + "-b", svg(b), (W / 2, b2 - 0.73 * s2))}</div>')
    size = fit(words, S)
    t = text_el(words, size, Y_C + X_HEIGHT * size / 2, light)
    return f'<div id="{cid}" class="card" data-layout-allow-overflow>{layer(cid + "-a", svg(t), (W / 2, Y_C))}</div>'


def smear_layer(c):
    return {"smear": "a", "pair-smear": "b"}.get(c["fx"])


def motion(c):
    cid, t0, t1, fx = c["id"], c["t0"], c["t1"], c["fx"]
    d = round(t1 - t0, 3)
    js = [f'tl.set("#{cid}", {{ visibility: "visible" }}, {t0});', f'tl.set("#{cid}", {{ visibility: "hidden" }}, {t1});']
    a, b = f'"#{cid}-a"', f'"#{cid}-b"'
    smear = (f'tl.fromTo("#{cid}-smear", {{ attr: {{ stdDeviation: "18 0" }} }}, '
             f'{{ attr: {{ stdDeviation: "0 0" }}, duration: 0.067, ease: "power1.in" }}, {t0});')
    if fx in ("settle", "stack"):  # lands a little big and settles for as long as it stays
        js.append(f'tl.fromTo({a}, {{ scale: 1.07 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
    elif fx == "focus":  # out of focus for three frames, then sharp, still settling
        js.append(f'tl.fromTo({a}, {{ scale: 1.14 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
        js.append(f'tl.fromTo({a}, {{ filter: "blur(16px)" }}, {{ filter: "blur(0px)", duration: 0.1, ease: "power1.in", immediateRender: false }}, {t0});')
    elif fx == "smear":  # a horizontal smear on its first two frames
        js.append(f'tl.fromTo({a}, {{ scale: 1.12 }}, {{ scale: 1, duration: {d}, ease: "power3.out" }}, {t0});')
        js.append(smear)
    elif fx == "pair":
        js.append(f'tl.fromTo({b}, {{ scale: 1.07 }}, {{ scale: 1, duration: {d}, ease: "power2.out" }}, {t0});')
    elif fx == "pair-smear":
        js.append(f'tl.fromTo({b}, {{ scale: 1.12 }}, {{ scale: 1, duration: {d}, ease: "power3.out" }}, {t0});')
        js.append(smear)
    elif fx == "eaten":  # held a few frames, then the blobs eat it; what is left goes with the cut
        e0 = t0 + ERASE_AFTER / FPS
        for j, (_, _, r, f0) in enumerate(BLOBS):
            js.append(f'tl.to("#{cid}-logo", {{ "--b{j}": "{r}px", duration: 0.1, ease: "power1.out" }}, {round(e0 + f0 / FPS, 3)});')
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
        tl.fromTo(".light", {{ scale: 1 }}, {{ scale: 1.04, duration: {LOOP}, ease: "none" }}, 0);
        // the sky (black words) and dusk (white words), flipped on every card
{flips}
        window.__timelines["fond"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def mots(C):
    smeared = [(c, smear_layer(c)) for c in C if smear_layer(c)]
    filters = "".join(f'<filter id="{c["id"]}-smear-f" x="-30%" y="-10%" width="160%" height="120%">'
                      f'<feGaussianBlur id="{c["id"]}-smear" stdDeviation="0 0" /></filter>' for c, _ in smeared)
    rules = "\n".join(f'        #{c["id"]}-{l} {{ filter: url(#{c["id"]}-smear-f); }}' for c, l in smeared)
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
        .layer {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
        .layer svg {{ position: absolute; left: 0; top: 0; overflow: visible; }}
        text {{ font-family: "Rise Sans", sans-serif; font-weight: 700; letter-spacing: {TRACK}em; }}
        .logo {{ position: absolute; height: auto; }}
{rules}
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
    <div id="stage" data-composition-id="main" data-start="0" data-duration="{LOOP}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
      <div id="fond" class="clip" data-composition-id="fond" data-composition-src="compositions/fond.html" data-start="0" data-duration="{LOOP}"
        data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <div id="mots" class="clip" data-composition-id="mots" data-composition-src="compositions/mots.html" data-start="0" data-duration="{LOOP}"
        data-track-index="2" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{LOOP}" data-track-index="3" data-volume="1"></audio>
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
        return " / ".join(w[:2]) if isinstance(w, tuple) else ("RISE (logo)" if w == "logo" else (w or ""))
    return {
        "category": "kinetic-type",
        "duration_s": LOOP,
        "fps": FPS,
        "canvas": {"w": W, "h": H, "aspect": "9:16"},
        "style": "the reference reel's edit, cut for cut on its own sound: one lowercase word at a time in a Helvetica-style bold "
                 "tracked tight, all the same size; every cut flips the light between the RISE sky (black words) and dusk "
                 "grey-blue (white words); words land a little big and settle, some out of focus or smeared; the statement with "
                 "a word landing under the one that stays; the list faster and faster; rise typed; the logo blown up and eaten "
                 "by blobs; an empty silent beat; loop",
        "palette": ["#93cdef", "#bfe3f6", "#def1fb", "#d0d1d7", "#95a0e0", "#717480", INK["sky"], INK["dusk"]],
        "font": "FreeSans Bold (GNU FreeFont, GPL with font exception), letter-spacing -0.035em",
        "beats": [frame(t) for t in CUTS],
        "export": "mp4",
        "asset_needs": [],
        "block": "caption-kinetic-slam",
        "customize": {"note": "its one-word-per-beat structure, rebuilt by tools/build.py on the reference's own cut times"},
        "content": {"scenes": [{"id": c["id"], "start": c["t0"], "end": c["t1"], "text": text(c), "motion": c["fx"],
                                "light": c["light"]} for c in C]},
    }


def main():
    assert len(CARDS) == len(CUTS)
    C = cards()
    (ROOT / "compositions").mkdir(exist_ok=True)
    (ROOT / "compositions" / "fond.html").write_text(fond(C))
    (ROOT / "compositions" / "mots.html").write_text(mots(C))
    (ROOT / "index.html").write_text(root())
    (ROOT / "shot-plan.json").write_text(json.dumps(shot_plan(C), ensure_ascii=False, indent=1) + "\n")
    for c in C:
        print(f"{c['t0']:6.3f}-{c['t1']:6.3f}  {c['light']:4s}  {c['fx']:10s} {c['words']}")
    print(f"{LOOP}s")


if __name__ == "__main__":
    main()
