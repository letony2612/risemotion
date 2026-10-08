"""Assemble index.html from tools/template.html and tools/timeline.py.

python3 tools/build.py            -> index.html (+ sound design and music beds)
python3 tools/build.py --no-audio -> index.html only
"""
import html
import json
import math
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402

ROOT = T.ROOT


def letters(word):
    return "".join(f'<span class="ch">{html.escape(c)}</span>' for c in word)


def dots(n=14):
    out = []
    for i in range(n):
        color = "#F59E0B" if i % 2 else "#1A1714"
        size = 16 if i % 3 else 22
        out.append(f'<span class="hdot" style="left: 540px; top: 970px; width: {size}px; height: {size}px; '
                   f'margin: -{size // 2}px 0 0 -{size // 2}px; background: {color}"></span>')
    return "".join(out)


def flames(n=10):
    return "".join('<img class="mini-flame" src="assets/ui/flame.png" alt="" style="left: 236px; top: 1034px" />'
                   for _ in range(n))


def confetti(n=26):
    return "".join('<span class="conf"></span>' for _ in range(n))


VERSE = "« Il est comme un arbre planté près des eaux, Et qui étend ses racines vers le courant… »"


def verse_words():
    return " ".join(f'<span class="vw">{html.escape(w)}</span>' for w in VERSE.split())


def captions(W):
    out = []
    track = 8
    for line, chunks in T.CHUNKS.items():
        words = W[line]
        for ci, (a, b) in enumerate(chunks):
            seg = words[a : b + 1]
            start = round(seg[0]["t"] - 0.06, 3)
            # hold until the next chunk takes its place (or a short tail after the last word)
            if ci + 1 < len(chunks):
                end = words[chunks[ci + 1][0]]["t"] - 0.07
            else:
                end = seg[-1]["e"] + 0.4
            dur = round(max(0.2, end - start), 3)
            spans = "".join(
                f'<span class="cw{" k" if keyword(w["w"]) else ""}" data-t="{w["t"]}">{html.escape(w["w"])}</span>'
                for w in seg)
            out.append(f'      <div id="cap-{line}-{ci}" class="clip cap" data-start="{start}" data-duration="{dur}" '
                       f'data-track-index="{track}"><div class="pill">{spans}</div></div>')
    return "\n".join(out)


def keyword(word):
    import re
    return re.sub(r"[^\w’'-]", "", word.lower()) in T.KEYWORDS


def audio_tags():
    tags = []
    for key in T.LINES:
        start = T.VO_START[key]
        f = ROOT / "assets" / "vo" / f"{key}.wav"
        dur = round(sf.info(str(f)).duration, 3)
        tags.append(f'      <audio id="vo-{key}" src="assets/vo/{key}.wav" data-start="{start}" data-duration="{dur}" '
                    f'data-track-index="10" data-volume="1"></audio>')
    tags.append(f'      <audio id="music" src="assets/audio/music.wav" data-start="0" data-duration="{T.DURATION}" '
                f'data-track-index="11" data-volume="0.45"></audio>')
    tags.append(f'      <audio id="sfx" src="assets/audio/sfx.wav" data-start="0" data-duration="{T.DURATION}" '
                f'data-track-index="12" data-volume="0.75"></audio>')
    return "\n".join(tags)


def main():
    W = T.words()
    E = T.events(W)
    tpl = (ROOT / "tools" / "template.html").read_text()
    rep = {
        "@@ENSEMBLE_LETTERS@@": letters("ensemble."),
        "@@PARTAGE_LETTERS@@": letters("Partage"),
        "@@HOOK_DOTS@@": dots(),
        "@@PRAY_FLAMES@@": flames(),
        "@@CONFETTI@@": confetti(),
        "@@CONFETTI8@@": confetti(),
        "@@VERSE_WORDS@@": verse_words(),
        "@@CAPTIONS@@": captions(W),
        "@@AUDIO@@": audio_tags(),
        "/*@@DATA@@*/": "const E = " + json.dumps(E) + f"; const D = {T.DURATION};",
        "@@DURATION@@": str(T.DURATION),
        "@@FIL_START@@": str(E["hook_out"]),
        "@@FIL_DUR@@": str(round(E["screen_publish"] - E["hook_out"], 3)),
        "@@PUB_START@@": str(E["screen_publish"]),
        "@@PUB_DUR@@": str(round(E["share_out"] + 0.6 - E["screen_publish"], 3)),
    }
    for k, v in rep.items():
        assert k in tpl, k
        tpl = tpl.replace(k, v)
    (ROOT / "index.html").write_text(tpl)
    (ROOT / "tools" / "events.json").write_text(json.dumps({"events": E, "words": W}, ensure_ascii=False, indent=1))
    print(f"index.html written: {T.DURATION}s, {len(E)} events")
    if "--no-audio" not in sys.argv:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "tools" / "sfx.py")], check=True)
        subprocess.run([sys.executable, str(ROOT / "tools" / "compose_music.py")], check=True)
    # duck the music under the voice (HyperFrames voice-over carve)
    import subprocess
    carve = ROOT.parent.parent / ".claude" / "skills" / "hyperframes-audio" / "scripts" / "carve.mjs"
    if carve.exists():
        voices = sum((["--voice", f"vo-{k}"] for k in T.LINES), [])
        for bed, strength in (("music", "0.6"), ("sfx", "0.6")):
            subprocess.run(["node", str(carve), "--comp", str(ROOT / "index.html"), "--bed", bed, "--strength", strength, *voices],
                           check=True, capture_output=True)
        print("music and effects carved under the voice-over")


if __name__ == "__main__":
    main()
