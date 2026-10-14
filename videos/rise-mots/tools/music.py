"""The reel's music: a minimal deep groove made for it (music/lyria_105bpm.mp3, Lyria 3.5, 105 BPM).

The track: three bars of a quiet pulse, one bar of break (a hit, silence, a riser), the groove from bar 4,
and one clean final hit on bar 26. The reel takes the last two beats of the pulse ("r… ri. ris rise." is
typed on them), the break ("rise." blown up on the hit, eaten in the silence, then "le réseau social"
on the riser), two bars of groove from the drop, and jumps on the bar line to the final hit for the logo.
Usage: python3 tools/music.py  -> assets/music.wav
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "music" / "lyria_105bpm.mp3"
SR = 48000
BEAT = 60 / 105
PHASE = 0.087  # the first beat's attack
START = 10  # the beat the reel opens on: bar 2, beat 3
DROP_END = 24  # the groove is kept up to bar 6's line
FINAL = 104  # bar 26: the final hit
TAIL = 2.3  # seconds kept from the final hit: its ring
LEAD = 0.010  # every cut sits this far before the beat's attack
XFADE = 0.02


def main():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "m.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-ar", str(SR), "-ac", "2", str(wav)], check=True)
        x, _ = sf.read(wav, always_2d=True)
    at = lambda beat: int(round((PHASE + beat * BEAT - LEAD) * SR))
    f = int(XFADE * SR)
    a = x[at(START): at(DROP_END) + f].copy()
    b = x[at(FINAL): at(FINAL) + int(TAIL * SR)].copy()
    ramp = np.sin(np.linspace(0, np.pi / 2, f))[:, None]  # equal-power join just before the bar line
    joint = a[-f:] * ramp[::-1] + b[:f] * ramp
    y = np.concatenate([a[:-f], joint, b[f:]])
    n = int(0.2 * SR)
    y[-n:] *= np.cos(np.linspace(0, np.pi / 2, n))[:, None]
    y[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))[:, None]
    y = y / np.max(np.abs(y)) * 0.89
    sf.write(ROOT / "assets" / "music.wav", y, SR)
    print(f"music: {len(y) / SR:.3f}s; beats at {LEAD:.3f} + k*{BEAT:.4f}s; final hit at {(DROP_END - START) * BEAT:.3f}s")


if __name__ == "__main__":
    main()
