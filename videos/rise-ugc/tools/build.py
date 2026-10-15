"""« RISE » UGC test: a TikTok-native ad, real people on their phones, the real app, TikTok text, the logo.

It should look like a creator's video rather than an ad: footage of people on their phones (free stock clips,
see BRIEF.md) and screen recordings of the real app, cut on the beat of the RISE track, with TikTok's own kind
of text (black words on white, one rounded box per line) carrying one sentence across the shots: « Tu cherches
d'autres chrétiens avec qui parler de ta foi ? », and what one does on RISE. Then the end card of the word reel
(videos/rise-mots): on black, the RISE logo animation, a heavy boom when its letters burst out, « Élevons-nous
ensemble. », « Disponible sur les stores » and the badges.
Usage: python3 tools/build.py  -> index.html
(python3 tools/prepare.py first, for the footage; tools/music.py for the sound)
"""
import html
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parents[1] / "RISE_presentation" / "4_clips"  # the real app's screen recordings, on a demo database
FOOTAGE = ROOT / "footage"  # the people clips as downloaded (not in git; their sources are in BRIEF.md)
FPS, W, H = 30, 1080, 1920
BPM, DROP = 124, 34.95  # the RISE track: its tempo, and the attack of its drop (bar 18), where the reel starts
BEAT = 60 / BPM

# the shots, in order: the footage and where the shot starts in it (s), how many beats it lasts, the words over
# it (\n: a new line) and the height of their middle, and the point the slow push-in heads for. People clips that
# are wider than 9:16 are cropped around cx (0 left, 1 right).
SHOTS = [
    dict(id="seul", src=FOOTAGE / "seul.mp4", at=0.0, beats=6, y=640, to=(540, 960),
         text="Tu cherches d'autres\nchrétiens avec qui\nparler de ta foi ?"),
    dict(id="fil", src=APP / "01_fil.mp4", at=1.5, beats=4, y=700, to=(540, 900),  # the feed, scrolling
         text="Sur RISE, tu partages\nce que tu vis"),
    dict(id="amis", src=FOOTAGE / "amis.mp4", at=0.0, beats=4, y=640, to=(540, 960),
         text="tu rejoins des groupes"),
    dict(id="groupe", src=APP / "03_groupe.mp4", at=5.75, beats=6, y=300, to=(540, 1050),  # a message typed, sent
         text="tu parles avec\nd'autres croyants"),
    dict(id="priere", src=APP / "02_priere.mp4", at=0.9, beats=4, y=1240, to=(300, 620),  # « Je prie »: 13 -> 14
         text="et on prie les uns\npour les autres"),
    dict(id="sourire", src=FOOTAGE / "sourire.mp4", at=0.0, beats=4, y=640, to=(540, 960),
         text="Le réseau social créé\npar un chrétien,\npour les chrétiens"),
]
CAP_SIZE = 58  # TikTok's text, at the size it has on a 1080-wide video
PUSH = 1.06  # every shot moves in a little while it plays

# the end card, as in videos/rise-mots: on black, the logo animation (960x500, its logo 920 px wide at rest),
# the slogan, « Disponible sur les stores » and the badges. The animation starts 0.2 s in (its candle already up);
# its letters burst out 0.667 s in: the boom lands there.
END_LEN = 3.3
SPLASH = dict(src="assets/brand/rise_splash_dark.webm", w=960, h=500, scale=0.82, cx=480, cy=317, at=810)
SPLASH_FROM, BURST = 0.2, 0.667
FONT_FILE = ROOT / "assets" / "fonts" / "FreeSansBold.ttf"
TRACK = -0.035  # letter-spacing of the end card's words, em
FLAME = "#ff6d00"  # the slogan's second word: the colour of the logo's flame
END_INK, STORES_INK = "#ffffff", "#b0b0b0"
SLOGAN = (("Élevons-nous", 0.6), ("ensemble.", 0.75))  # a word, the seconds after the boom
SLOGAN_SIZE, SLOGAN_BASE = 64, 1028
STORES = ("Disponible sur les stores", 0.95)  # the line over the badges, the seconds after the boom
STORES_SIZE, STORES_BASE = 40, 1113
BADGES = (("assets/brand/badge_app_store_fr.png", "Télécharger dans l'App Store", 1.1),
          ("assets/brand/badge_google_play_fr.png", "Disponible sur Google Play", 1.2))
FLAME_AT = (365, 205)  # the flame, in the logo animation's own pixels: the warm light of the boom starts there
BADGE_W, BADGE_H, BADGE_GAP, BADGE_TOP = 400, 133, 26, 1145


def frame(t):
    return round(t * FPS) / FPS


def r3(t):
    return round(t, 3)


def timeline():
    """Each shot's start and end, on the beat; and when the end card starts."""
    out, beats = [], 0
    for s in SHOTS:
        t0, t1 = frame(beats * BEAT), frame((beats + s["beats"]) * BEAT)
        out.append(dict(s, t0=t0, t1=t1, d=r3(t1 - t0)))
        beats += s["beats"]
    return out, frame(beats * BEAT)


TIMED, END_T0 = timeline()
DURATION = frame(END_T0 + END_LEN)
BOOM_AT = frame(END_T0 + BURST - SPLASH_FROM)  # tools/music.py mixes the boom here


def font(size):
    return ImageFont.truetype(str(FONT_FILE), size)


def pens(text, size):
    """Each glyph's pen x from the line's start, kerned and tracked as the browser sets it."""
    f = font(size)
    return [f.getlength(text[: i + 1]) - f.getlength(ch) + i * TRACK * size for i, ch in enumerate(text)]


class Line:
    """A line of the end card, centred: its glyphs and where each one sits."""

    def __init__(self, text, size, base):
        self.text, self.size, self.base = text, size, base
        f = font(size)
        self.left = (W - (f.getlength(text) + TRACK * size * (len(text) - 1))) / 2
        self.glyphs = [(k, ch, self.left + x) for k, (ch, x) in enumerate(zip(text, pens(text, size))) if ch != " "]


def shot_html(s):
    lines = "<br>".join(f"<span>{html.escape(line)}</span>" for line in s["text"].split("\n"))
    video = (f'<video id="v-{s["id"]}" class="clip" src="assets/shots/{s["id"]}.mp4" muted playsinline data-start="{s["t0"]}" '
             f'data-duration="{s["d"]}" data-media-start="0" data-track-index="1"></video>'
             if (ROOT / "assets" / "shots" / f'{s["id"]}.mp4').exists() else "")
    return (f'      <div id="w-{s["id"]}" class="shotw" style="transform-origin: {s["to"][0]}px {s["to"][1]}px">{video}</div>\n'
            f'      <div id="cap-{s["id"]}" class="cap" style="top: {s["y"]}px"><p>{lines}</p></div>')


def shot_js(s):
    cap = f'"#cap-{s["id"]}"'
    return [f'tl.fromTo("#w-{s["id"]}", {{ scale: 1 }}, {{ scale: {PUSH}, duration: {s["d"]}, ease: "none" }}, {s["t0"]});',
            f'tl.set({cap}, {{ visibility: "visible" }}, {s["t0"]});',
            f'tl.set({cap}, {{ visibility: "hidden" }}, {s["t1"]});',
            # TikTok's text is just there on the cut; a small pop makes it land
            f'tl.fromTo("#cap-{s["id"]} p", {{ scale: 0.86 }}, {{ scale: 1, duration: 0.2, ease: "back.out(2.2)" }}, {s["t0"]});']


def end_card(t0):
    """The logo animation and its boom, the slogan under it, « Disponible sur les stores » and the two store
    badges, on black: HTML, CSS and tweens."""
    sw, sh, k = SPLASH["w"], SPLASH["h"], SPLASH["scale"]
    left, top = W / 2 - SPLASH["cx"] * k, SPLASH["at"] - SPLASH["cy"] * k
    dur = r3(DURATION - t0)

    def text(line, glyphs, fill):
        return "".join(f'<text data-layout-allow-overlap x="{x:.1f}" y="{line.base:.1f}" style="font-size: {line.size}px; fill: {fill}">{html.escape(ch)}</text>'
                       for _, ch, x in glyphs)

    def mask(mid, line):  # a baseline mask: the line's words rise from under it
        top_m, bot_m = line.base - 1.05 * line.size, line.base + 0.3 * line.size
        return f'<clipPath id="{mid}"><rect x="0" y="{top_m:.0f}" width="{W}" height="{bot_m - top_m:.0f}" /></clipPath>'

    line = Line(" ".join(t for t, _ in SLOGAN), SLOGAN_SIZE, SLOGAN_BASE)
    words, start = [], 0
    for j, (word, _) in enumerate(SLOGAN):  # each word of the slogan rises on its own
        glyphs = [g for g in line.glyphs if start <= g[0] < start + len(word)]
        start += len(word) + 1
        words.append(f'<g id="slogan{j}">{text(line, glyphs, FLAME if j else END_INK)}</g>')
    stores = Line(STORES[0], STORES_SIZE, STORES_BASE)
    slogan = (f'<svg id="slogan" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{mask("slogan-clip", line)}{mask("stores-clip", stores)}'
              f'<g clip-path="url(#slogan-clip)">{"".join(words)}</g>'
              f'<g clip-path="url(#stores-clip)"><g id="stores">{text(stores, stores.glyphs, STORES_INK)}</g></g></svg>')
    bx = (W - 2 * BADGE_W - BADGE_GAP) / 2
    badges = "".join(f'<img id="badge{j}" class="badge" src="{src}" alt="{html.escape(alt)}" '
                     f'style="left: {bx + j * (BADGE_W + BADGE_GAP):.0f}px; top: {BADGE_TOP}px" />' for j, (src, alt, _) in enumerate(BADGES))
    body = f"""      <div id="noir" class="clip" data-start="{t0}" data-duration="{dur}" data-track-index="3"></div>
      <div id="fin" data-layout-allow-overflow>
        <div id="flash"></div>
        <div id="splashw"><video id="splash" class="clip" src="{SPLASH["src"]}" muted playsinline data-start="{t0}" data-duration="{dur}" data-media-start="{SPLASH_FROM}" data-track-index="4"></video></div>
        {slogan}
        {badges}
      </div>"""
    fx, fy = left + FLAME_AT[0] * k, top + FLAME_AT[1] * k
    css = f"""      #noir {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; background: #000000; }}
      #fin {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #flash {{ position: absolute; left: {fx - 520:.0f}px; top: {fy - 520:.0f}px; width: 1040px; height: 1040px; visibility: hidden;
        background: radial-gradient(closest-side, rgba(255, 168, 60, 0.6), rgba(255, 200, 120, 0.25) 45%, rgba(255, 255, 255, 0)); }}
      #splashw {{ position: absolute; left: {left:.0f}px; top: {top:.0f}px; width: {sw * k:.0f}px; height: {sh * k:.0f}px; transform-origin: {SPLASH["cx"] * k:.0f}px {SPLASH["cy"] * k:.0f}px; }}
      #splash {{ position: absolute; left: 0; top: 0; width: {sw * k:.0f}px; height: {sh * k:.0f}px; display: block; }}
      #slogan {{ position: absolute; left: 0; top: 0; overflow: visible; }}
      #slogan text {{ font-family: "Rise Sans", sans-serif; font-weight: 700; }}
      .badge {{ position: absolute; width: {BADGE_W}px; height: {BADGE_H}px; display: block; opacity: 0; }}"""
    js = [f'tl.fromTo("#splashw", {{ scale: 0.96 }}, {{ scale: 1.03, duration: {dur}, ease: "sine.out" }}, {t0});']
    # the boom: a warm light spreads from the flame over the black as the letters burst out
    b = BOOM_AT
    js.append(f'tl.set("#flash", {{ visibility: "visible" }}, {b});')
    js.append(f'tl.fromTo("#flash", {{ opacity: 1, scale: 0.35 }}, {{ opacity: 0, scale: 1.6, duration: 1.0, ease: "power2.out" }}, {b});')
    js.append(f'tl.set("#flash", {{ visibility: "hidden" }}, {r3(b + 1.0)});')
    for j, (_, at) in enumerate(SLOGAN):
        js.append(f'tl.fromTo("#slogan{j}", {{ y: {1.4 * SLOGAN_SIZE:.0f} }}, {{ y: 0, duration: 0.5, ease: "expo.out" }}, {r3(b + at)});')
    js.append(f'tl.fromTo("#stores", {{ y: {1.4 * STORES_SIZE:.0f} }}, {{ y: 0, duration: 0.5, ease: "expo.out" }}, {r3(b + STORES[1])});')
    for j, (_, _, at) in enumerate(BADGES):
        js.append(f'tl.fromTo("#badge{j}", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "expo.out" }}, {r3(b + at)});')
    return body, css, js


def root():
    body, css, js = end_card(END_T0)
    shots = "\n".join(shot_html(s) for s in TIMED)
    script = "\n".join("      " + j for j in [j for s in TIMED for j in shot_js(s)] + js)
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Rise Sans"; font-weight: 700; src: url("assets/fonts/FreeSansBold.ttf") format("truetype"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000000; }}
      #stage {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000000; }}
      .shotw {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      .shotw video {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; display: block; }}
      .cap {{ position: absolute; left: 0; width: {W}px; transform: translateY(-50%); text-align: center; visibility: hidden; }}
      .cap p {{ display: inline-block; font-family: "Rise Sans", sans-serif; font-weight: 700; font-size: {CAP_SIZE}px; line-height: 1.32;
        letter-spacing: -0.01em; color: #121212; filter: drop-shadow(0 6px 18px rgba(0, 0, 0, 0.22)); }}
      .cap span {{ background: #ffffff; padding: 4px 22px 6px; border-radius: 16px; box-decoration-break: clone; -webkit-box-decoration-break: clone; }}
{css}
    </style>
  </head>
  <body>
    <div id="stage" data-composition-id="main" data-start="0" data-duration="{DURATION}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
{shots}
{body}
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{DURATION}" data-track-index="5" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
{script}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def main():
    (ROOT / "index.html").write_text(root())
    for s in TIMED:
        ok = (ROOT / "assets" / "shots" / f'{s["id"]}.mp4').exists()
        print(f'{s["t0"]:6.3f}-{s["t1"]:6.3f}  {s["id"]:8s} {"" if ok else "(no footage yet) "}{s["text"].replace(chr(10), " / ")}')
    print(f"{END_T0:6.3f}-{DURATION:6.3f}  end card, the boom at {BOOM_AT:.3f}")


if __name__ == "__main__":
    main()
