"""Single-stroke letters, to write words as drawings: the Hershey fonts (public domain, A. V. Hershey, 1967), via
the Hershey-Fonts package, exported once for the printable ASCII characters so the episodes need nothing else.
- scripts: a simple cursive, for handwriting (the teacher's comment);
- futural: a simple sans, for what is printed or written in capitals (the report card's headings, marks).
French accents are drawn by the episodes on top of the plain letters (é è ê î ç à ...).
Usage: pip install Hershey-Fonts; python3 tools/hershey_export.py  -> assets/hershey.json
"""
import json
from pathlib import Path

from HersheyFonts import HersheyFonts

ROOT = Path(__file__).resolve().parents[1]
FONTS = ("scripts", "futural")


def first_x(strokes):
    return min(x for s in strokes for x, _ in s) if strokes else 0


def main():
    out = {}
    for name in FONTS:
        f = HersheyFonts()
        f.load_default_font(name)
        ref = list(f.strokes_for_text("l"))
        ref_x = first_x(ref)
        glyphs = {}
        for code in range(32, 127):
            ch = chr(code)
            alone = [list(map(list, s)) for s in f.strokes_for_text(ch)]
            pair = list(f.strokes_for_text(ch + "l"))
            l_strokes = pair[len(alone):]
            adv = first_x(l_strokes) - ref_x if l_strokes else 0
            glyphs[ch] = {"s": alone, "a": adv}
        out[name] = glyphs
    (ROOT / "assets" / "hershey.json").write_text(json.dumps(out, separators=(",", ":")))
    print("assets/hershey.json:", {k: len(v) for k, v in out.items()}, "advance of 'm' in scripts:", out["scripts"]["m"]["a"])


if __name__ == "__main__":
    main()
