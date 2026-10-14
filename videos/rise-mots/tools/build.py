"""The reel « rise » — RISE in a few words, one at a time, cut on the music's beat.

At every cut the light flips between the sky of the RISE site (blue, soft clouds, a blurred cross;
black words) and a sunrise (amber, warm clouds, the same cross, fainter; white words). The grammar
follows the reference reel the user sent: letters typed one by one, a word blown up to the edges
that breaks apart, a small word over a big one, a motion blur; it ends on the RISE logo.
Usage: python3 tools/build.py  -> index.html, compositions/fond.html, compositions/mots.html
(then python3 tools/music.py and tools/backdrop.py only if the music or the sky change)
"""
import html
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
BEAT = 60 / 124  # the music's tempo (tools/music.py)
FPS = 30
# (beat, words, effect): a word, or (small word, big word) stacked; the light flips at every step
STEPS = [
    (0, "r", "cut"),
    (1, "ri", "cut"),
    (2, "ris", "cut"),
    (3, "rise.", "cut"),
    (4, "rise.", "punch"),  # the groove kicks in: the word fills the frame, then breaks apart
    (5, ("le réseau", "social"), "mblur"),
    (6, "chrétien.", "pop"),
    (8, "partage", "settle"),
    (9, "entraide", "settle"),
    (10, "prière", "settle"),
    (11, "quiz", "settle"),
    (12, "verset", "settle"),
    (13, "créé", "blur"),
    (14, ("par un", "chrétien"), "warp"),
    (16, "pour", "cut"),
    (17, ("les", "chrétiens."), "slam"),
    (20, None, "logo"),  # the track jumps to its last bar here (tools/music.py)
]
SLOGAN = ("Élève-toi.", "Ensemble.")
DURATION = round((20 * BEAT + 2.02) * FPS) / FPS
W, H = 1080, 1920
FONT = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "InterDisplay-Bold.otf"), 200)
TRACK = -0.05  # letter-spacing, em
WORD_MAX, WORD_W = 290, 880  # a word: at most 290 px, and no wider than the title-safe width
PUNCH_W = 1000  # the blown-up word reaches the edges
SMALL = 0.42  # the small word of a pair, against the big one


def frame(t):
    return round(t * FPS) / FPS


def width(text, size):
    return FONT.getlength(text) * size / 200 + TRACK * size * (len(text) - 1)


def fit(text, max_size, max_w):
    return round(min(max_size, max_size * max_w / width(text, max_size)), 1)


def steps():
    out = []
    for i, (beat, words, fx) in enumerate(STEPS):
        t0 = frame(beat * BEAT)
        t1 = frame(STEPS[i + 1][0] * BEAT) if i + 1 < len(STEPS) else DURATION
        out.append(dict(i=i, t0=t0, t1=t1, words=words, fx=fx, amber=i % 2 == 1))
    return out


def word_html(s):
    on = "on-amber" if s["amber"] else "on-sky"
    if s["fx"] == "logo":
        a, b = SLOGAN
        return (f'<div id="w{s["i"]}" class="w {on} logo"><div class="logo-box"><span id="glow" class="glow"></span>'
                f'<img id="logo" src="assets/rise_logo.png" alt="RISE" /></div>'
                f'<div id="slogan" class="slogan">{html.escape(a)} <em>{html.escape(b)}</em></div></div>')
    if isinstance(s["words"], tuple):
        small, big = s["words"]
        size = fit(big, WORD_MAX, WORD_W)
        return (f'<div id="w{s["i"]}" class="w {on} pair" data-layout-allow-overflow>'
                f'<div class="top" style="font-size: {round(size * SMALL, 1)}px">{html.escape(small)}</div>'
                f'<div class="big" style="font-size: {size}px">{html.escape(big)}</div></div>')
    size = fit(s["words"], 560, PUNCH_W) if s["fx"] == "punch" else fit(s["words"], WORD_MAX, WORD_W)
    return (f'<div id="w{s["i"]}" class="w {on}" data-layout-allow-overflow>'
            f'<div class="big" style="font-size: {size}px">{html.escape(s["words"])}</div></div>')


def fond(S):
    # the cross is the same light on both, as faint on the sunrise as it is soft on the sky
    flips = "\n".join(f'        tl.set("#sunrise", {{ visibility: "{"visible" if s["amber"] else "hidden"}" }}, {s["t0"]});\n'
                      f'        tl.set("#cross", {{ opacity: {0.1 if s["amber"] else 0.95} }}, {s["t0"]});' for s in S)
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    <template>
      <style>
        #root {{ position: absolute; inset: 0; overflow: hidden; }}
        .light {{ position: absolute; inset: 0; overflow: hidden; }}
        #sky {{ background: linear-gradient(180deg, var(--sky-top), var(--sky-bottom)); }}
        #sunrise {{ background: linear-gradient(180deg, var(--sun-top), var(--sun-bottom)); visibility: hidden; }}
        .clouds {{ position: absolute; left: -100px; top: -100px; width: 1280px; height: 2120px; }}
        #sky .clouds {{ opacity: 0.9; }}
        #sunrise .clouds {{ opacity: 0.25; }}
        #cross {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; opacity: 0.95; }}
        #root {{
          --sky-top: #9fd3f0;
          --sky-bottom: #d9effa;
          --sun-top: #e3470a;
          --sun-bottom: #f7801a;
        }}
      </style>
      <div id="root" data-composition-id="fond" data-width="{W}" data-height="{H}">
        <div id="sky" class="light">
          <img class="clouds" src="assets/clouds_white.png" alt="" data-layout-allow-overflow />
        </div>
        <div id="sunrise" class="light">
          <img class="clouds" src="assets/clouds_warm.png" alt="" data-layout-allow-overflow />
        </div>
        <img id="cross" src="assets/cross.png" alt="" data-layout-allow-overflow />
      </div>
      <script>
        window.__timelines = window.__timelines || {{}};
        const tl = gsap.timeline({{ paused: true }});
        // the clouds drift the whole time, the same in both lights: a cut changes the light, not the place
        tl.fromTo(".clouds", {{ x: 0, y: 0 }}, {{ x: -80, y: -40, duration: {DURATION}, ease: "none" }}, 0);
        tl.fromTo("#cross", {{ scale: 1 }}, {{ scale: 1.03, duration: {DURATION}, ease: "none" }}, 0);
        // the light flips at every word: sky (black words), sunrise (white words)
{flips}
        window.__timelines["fond"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def mots(S):
    words = "\n        ".join(word_html(s) for s in S)
    js = []
    for s in S:
        el, t0, t1, fx = f'"#w{s["i"]}"', s["t0"], s["t1"], s["fx"]
        js.append(f"        tl.set({el}, {{ visibility: \"visible\" }}, {t0});")
        if fx != "logo":
            js.append(f"        tl.set({el}, {{ visibility: \"hidden\" }}, {t1});")
        big, top = f'"#w{s["i"]} .big"', f'"#w{s["i"]} .top"'
        if fx == "punch":
            js.append(f'        tl.fromTo({big}, {{ scale: 1.08 }}, {{ scale: 1, duration: 0.2, ease: "power2.out" }}, {t0});')
            js.append(f'        tl.fromTo("#breakup", {{ attr: {{ scale: 0 }} }}, {{ attr: {{ scale: 90 }}, duration: 0.17, ease: "power2.in" }}, {round(t1 - 0.17, 3)});')
            js.append(f'        tl.to({big}, {{ opacity: 0, duration: 0.17, ease: "power2.in" }}, {round(t1 - 0.17, 3)});')
        elif fx == "mblur":
            js.append(f'        tl.fromTo({big}, {{ x: 240 }}, {{ x: 0, duration: 0.2, ease: "power3.out" }}, {t0});')
            js.append(f'        tl.fromTo("#streak", {{ attr: {{ stdDeviation: "60 0" }} }}, {{ attr: {{ stdDeviation: "0 0" }}, duration: 0.2, ease: "power3.out" }}, {t0});')
        elif fx == "pop":
            js.append(f'        tl.fromTo({big}, {{ scale: 0.8 }}, {{ scale: 1, duration: 0.28, ease: "back.out(2.4)" }}, {t0});')
        elif fx == "settle":
            dy = 18 if s["i"] % 2 else -18
            js.append(f'        tl.fromTo({big}, {{ scale: 1.07, y: {dy} }}, {{ scale: 1, y: 0, duration: 0.22, ease: "power2.out" }}, {t0});')
        elif fx == "blur":
            js.append(f'        tl.fromTo({big}, {{ opacity: 0, filter: "blur(18px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.16, ease: "power2.out" }}, {t0});')
        elif fx == "warp":
            js.append(f'        tl.fromTo({top}, {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.16, ease: "power2.out" }}, {t0});')
            js.append(f'        tl.fromTo({big}, {{ skewX: -16, scaleX: 1.3 }}, {{ skewX: 0, scaleX: 1, duration: 0.24, ease: "power3.out" }}, {t0});')
        elif fx == "slam":
            js.append(f'        tl.fromTo({top}, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, ease: "power1.out" }}, {t0});')
            js.append(f'        tl.fromTo({big}, {{ y: -70, scale: 1.12 }}, {{ y: 0, scale: 1, duration: 0.2, ease: "power4.out" }}, {t0});')
        elif fx == "logo":
            js.append(f'        tl.fromTo("#logo", {{ opacity: 0, scale: 0.9, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "power3.out" }}, {t0});')
            js.append(f'        tl.fromTo("#glow", {{ opacity: 0, scale: 0.5 }}, {{ opacity: 0.9, scale: 1.1, duration: 0.5, ease: "power2.out" }}, {t0 + 0.05:.3f});')
            js.append(f'        tl.to("#glow", {{ opacity: 0.55, scale: 1, duration: 0.9, ease: "sine.inOut" }}, {t0 + 0.55:.3f});')
            js.append(f'        tl.fromTo("#slogan", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, {t0 + 0.3:.3f});')
            js.append(f'        tl.fromTo("#w{s["i"]} .logo-box", {{ scale: 1 }}, {{ scale: 1.03, duration: {round(DURATION - t0, 3)}, ease: "none" }}, {t0});')
    script = "\n".join(js)
    # the break-up and the streak are SVG filters on the one word that uses each
    filters = "\n".join(f'        #w{s["i"]} .big {{ filter: url(#{ {"punch": "breakup", "mblur": "streak"}[s["fx"]] }-filter); }}'
                        for s in S if s["fx"] in ("punch", "mblur"))
    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    <template>
      <style>
        @font-face {{ font-family: "Inter Display"; font-weight: 700; src: url("assets/fonts/InterDisplay-Bold.otf") format("opentype"); }}
        @font-face {{ font-family: "Inter Display"; font-weight: 600; src: url("assets/fonts/InterDisplay-SemiBold.otf") format("opentype"); }}
        #root {{
          position: absolute;
          inset: 0;
          --ink-sky: #111111;
          --ink-sun: #ffffff;
          --amber: #b64400;
        }}
        .w {{
          position: absolute;
          left: 0;
          top: 0;
          width: {W}px;
          height: {H}px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding-bottom: 120px;
          box-sizing: border-box;
          visibility: hidden;
          font-family: "Inter Display", sans-serif;
          font-weight: 700;
          letter-spacing: {TRACK}em;
          line-height: 0.9;
          white-space: nowrap;
        }}
        .on-sky {{ color: var(--ink-sky); }}
        .on-amber {{ color: var(--ink-sun); }}
        .big {{ display: block; }}
        .top {{ display: block; margin-bottom: -0.02em; }}
{filters}
        .logo-box {{ position: relative; width: 640px; }}
        #logo {{ display: block; width: 640px; height: auto; }}
        .glow {{
          position: absolute;
          left: 179px;
          top: -38px;
          width: 120px;
          height: 160px;
          border-radius: 50%;
          background: radial-gradient(closest-side, rgba(255, 170, 60, 0.85), rgba(255, 170, 60, 0));
          filter: blur(14px);
        }}
        .slogan {{
          margin-top: 54px;
          font-family: "Inter Display", sans-serif;
          font-weight: 700;
          font-size: 70px;
          letter-spacing: -0.04em;
          color: #1d1d1f;
        }}
        .slogan em {{ font-style: normal; color: var(--amber); }}
      </style>
      <div id="root" data-composition-id="mots" data-width="{W}" data-height="{H}">
        <svg width="0" height="0" style="position: absolute">
          <filter id="breakup-filter" x="-20%" y="-40%" width="140%" height="180%">
            <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="4" />
            <feDisplacementMap id="breakup" in="SourceGraphic" scale="0" xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <filter id="streak-filter" x="-30%" y="-10%" width="160%" height="120%">
            <feGaussianBlur id="streak" stdDeviation="0 0" />
          </filter>
        </svg>
        {words}
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
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #9fd3f0; }}
      #stage {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
    </style>
  </head>
  <body>
    <div id="stage" data-composition-id="main" data-start="0" data-duration="{DURATION}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
      <div id="fond" class="clip" data-composition-id="fond" data-composition-src="compositions/fond.html" data-start="0" data-duration="{DURATION}"
        data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <div id="mots" class="clip" data-composition-id="mots" data-composition-src="compositions/mots.html" data-start="0" data-duration="{DURATION}"
        data-track-index="2" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{DURATION}" data-track-index="3" data-volume="0.7"></audio>
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


def main():
    S = steps()
    (ROOT / "compositions").mkdir(exist_ok=True)
    (ROOT / "compositions" / "fond.html").write_text(fond(S))
    (ROOT / "compositions" / "mots.html").write_text(mots(S))
    (ROOT / "index.html").write_text(root())
    for s in S:
        print(f"{s['t0']:6.3f}-{s['t1']:6.3f}  {'sunrise' if s['amber'] else 'sky    '}  {s['fx']:7s} {s['words']}")
    print(f"{DURATION}s")


if __name__ == "__main__":
    main()
