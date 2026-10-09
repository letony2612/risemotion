"""Assemble index.html from tools/template.html and tools/timeline.py.

python3 tools/build.py              -> index.html (+ sound design and music beds)
python3 tools/build.py --no-audio   -> index.html only
python3 tools/build.py --until 6.6  -> a preview cut at 6.6 s (the edit itself is unchanged)
python3 tools/build.py --white      -> the same film on a plain white background
python3 tools/build.py --apple      -> the Apple-style cut: white, black headlines, softer motion, its own sound effects
"""
import html
import json
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402
from lifts import LIFTS  # noqa: E402

ROOT = T.ROOT
APPLE = "--apple" in sys.argv
SCREEN_W, BEZEL = 600, 18  # the phone screen in the composition (captures are 1080 px wide)


def bokeh():
    """Out-of-focus lights: (left, top, size, rgba)."""
    spots = [(-160, 120, 520, (255, 190, 110, 0.34)), (760, 40, 380, (255, 255, 255, 0.85)),
             (820, 560, 300, (255, 205, 140, 0.4)), (-80, 900, 260, (255, 255, 255, 0.8)),
             (600, 1180, 560, (255, 180, 100, 0.26)), (80, 1500, 360, (255, 214, 150, 0.34)),
             (880, 1600, 240, (255, 255, 255, 0.75)), (380, 300, 160, (255, 226, 180, 0.5)),
             (300, 1750, 200, (255, 200, 120, 0.3))]
    out = []
    for x, y, d, (r, g, b, a) in spots:
        out.append(f'<span class="bk" style="left: {x}px; top: {y}px; width: {d}px; height: {d}px; '
                   f'background: radial-gradient(closest-side, rgba({r}, {g}, {b}, {a}) 0%, rgba({r}, {g}, {b}, {a * 0.85:.2f}) 62%, '
                   f'rgba({r}, {g}, {b}, 0) 100%)"></span>')
    return "".join(out)


def hearts(n=6):
    return "".join('<span class="heart" style="left: 86px; top: 191px"><svg><use href="#heartShape" /></svg></span>'
                   for _ in range(n))


def mflames(n=8):
    return "".join('<img class="mflame" src="assets/ui/flame.png" alt="" style="left: 77px; top: 286px" />' for _ in range(n))


def confetti(n=26):
    return "".join('<span class="conf"></span>' for _ in range(n))


def nbsp(text, short=False):
    """French spacing: the space before ? ! : ; % stays with its word; with short=True, words of up to
    three letters also hold on to the next one, so a punch line never breaks after "du" or "ta"."""
    for p in "?!:;%":
        text = text.replace(f" {p}", f"\u00a0{p}")
    if short:
        words = text.split(" ")
        text = "".join(w + ("\u00a0" if len(w) <= 3 and i + 1 < len(words) else " ") for i, w in enumerate(words)).strip()
    return text


def beats(W, duration):
    """Two-tier captions: a setup label from the beat's first word, then each punch line on its own first word."""
    out, starts = [], []
    for line, setup, punches in T.BEATS:
        first = (setup or punches[0])[0]
        starts.append(round(W[line][first]["t"] - 0.08, 3))
    for bi, (line, setup, punches) in enumerate(T.BEATS):
        words = W[line]
        start = starts[bi]
        end = starts[bi + 1] if bi + 1 < len(starts) else duration
        parts = []
        if setup:
            text = " ".join(w["w"] for w in words[setup[0]: setup[1] + 1])
            text = html.escape(nbsp(text)).replace("RISE", "<b>RISE</b>")
            parts.append(f'<div class="row s"><span class="setup">{text}</span></div>')
        times = [round(words[a]["t"] - 0.04, 3) for a, _ in punches]
        for pi, (a, b) in enumerate(punches):
            text = T.PUNCH_TEXT.get((line, a)) or " ".join(w["w"] for w in words[a: b + 1])
            text = text.rstrip(",:")
            u = times[pi + 1] if pi + 1 < len(times) else end
            cls = "punch long" if len(text) > 18 else "punch"
            parts.append(f'<div class="row p"><span class="{cls}" data-t="{times[pi]}" data-u="{round(u, 3)}">'
                         f'{html.escape(nbsp(text, short=True))}</span></div>')
        out.append(f'      <div id="beat{bi}" class="clip beat" data-start="{start}" data-duration="{round(end - start, 3)}" '
                   f'data-track-index="8">{"".join(parts)}</div>')
    return "\n".join(out)


def positions():
    """Each lifted piece over its own pixels: in phone coordinates (POS) and screen coordinates (SPOS)."""
    s = SCREEN_W / 1080
    rep = {}
    for name, (_, (x0, y0, x1, y1), _) in LIFTS.items():
        box = lambda off: (f"left: {off + x0 * s:.1f}px; top: {off + y0 * s:.1f}px; "
                           f"width: {(x1 - x0) * s:.1f}px; height: {(y1 - y0) * s:.1f}px")
        rep[f"@@POS:{name}@@"] = box(BEZEL)
        rep[f"@@SPOS:{name}@@"] = box(0)
    return rep


def audio_tags(duration):
    tags = []
    for key in T.LINES:
        start = T.VO_START[key]
        if start >= duration:
            continue
        f = ROOT / "assets" / "vo" / f"{key}.wav"
        dur = round(min(sf.info(str(f)).duration, duration - start), 3)
        tags.append(f'      <audio id="vo-{key}" src="assets/vo/{key}.wav" data-start="{start}" data-duration="{dur}" '
                    f'data-track-index="10" data-volume="1"></audio>')
    # the Apple cut has fewer, sparser effects: music and effects a touch higher keep the same balance (~10 dB under the voice)
    music_vol, sfx, sfx_vol = ("0.7", "sfx_apple", "0.9") if APPLE else ("0.6", "sfx", "0.7")
    tags.append(f'      <audio id="music" src="assets/audio/music.wav" data-start="0" data-duration="{duration}" '
                f'data-track-index="11" data-volume="{music_vol}"></audio>')
    tags.append(f'      <audio id="sfx" src="assets/audio/{sfx}.wav" data-start="0" data-duration="{duration}" '
                f'data-track-index="12" data-volume="{sfx_vol}"></audio>')
    return "\n".join(tags)


def main():
    W = T.words()
    E = T.events(W)
    duration = T.DURATION
    if "--until" in sys.argv:
        duration = min(duration, float(sys.argv[sys.argv.index("--until") + 1]))
    tpl = (ROOT / "tools" / "template.html").read_text()
    splash_end = min(duration, E["phone_in"] + 0.5)
    rep = {
        "@@BOKEH@@": bokeh(),
        "@@HEARTS@@": hearts(),
        "@@CONFETTI@@": confetti(),
        "@@BEATS@@": beats(W, duration),
        "@@AUDIO@@": audio_tags(duration),
        "/*@@DATA@@*/": "const E = " + json.dumps(E) + f"; const D = {duration}; const APPLE = {json.dumps(APPLE)};",
        "@@DURATION@@": str(duration),
        "@@ROOT_CLASS@@": "white apple" if APPLE else "white" if "--white" in sys.argv else "",
        "@@SPLASH2_START@@": str(E["splash2"]),
        "@@SPLASH2_DUR@@": str(round(splash_end - E["splash2"], 3)),
        "@@SPLASH9_START@@": str(E["splash9"]),
        "@@SPLASH9_DUR@@": str(round(max(0.1, min(duration, E["splash9"] + 5.6) - E["splash9"]), 3)),
        "@@MFLAMES@@": mflames(),
        **positions(),
    }
    for k, v in rep.items():
        assert k in tpl or k.startswith(("@@POS:", "@@SPOS:")), k  # not every piece casts a shadow
        tpl = tpl.replace(k, v)
    assert "@@" not in tpl, tpl[tpl.index("@@") - 40: tpl.index("@@") + 40]
    (ROOT / "index.html").write_text(tpl)
    (ROOT / "tools" / "events.json").write_text(json.dumps({"events": E, "words": W}, ensure_ascii=False, indent=1))
    print(f"index.html written: {duration}s (film {T.DURATION}s), {len(E)} events")
    if "--no-audio" not in sys.argv:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "tools" / "sfx.py"), *(["--apple"] if APPLE else [])], check=True)
        subprocess.run([sys.executable, str(ROOT / "tools" / "compose_music.py")], check=True)
    # duck the music under the voice (HyperFrames voice-over carve)
    import subprocess
    carve = ROOT.parent.parent / ".claude" / "skills" / "hyperframes-audio" / "scripts" / "carve.mjs"
    if carve.exists():
        voices = sum((["--voice", f"vo-{k}"] for k in T.LINES if T.VO_START[k] < duration), [])
        # a light carve on the music only: the bed keeps its presence, the effects keep their punch
        for bed, strength in (("music", "0.45"),):
            subprocess.run(["node", str(carve), "--comp", str(ROOT / "index.html"), "--bed", bed, "--strength", strength, *voices],
                           check=True, capture_output=True)
        print("music and effects carved under the voice-over")


if __name__ == "__main__":
    main()
