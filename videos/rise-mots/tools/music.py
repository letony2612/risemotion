"""The reel's music: the RISE track (RISE_presentation/musique_Lyria.mp3, 124 BPM), cut on its bars.

The reel opens on the quiet bar before the groove (bar 17: "r… ri… ris… rise." is typed over it),
the groove kicks in on the next bar line, when "rise." fills the screen, and runs four bars; on the
logo the track jumps, on a bar line, to its last bar, so the reel ends on the music's own ending.
Beat grid from the track's analysis (videos/rise-presentation/assets/audio/music_track.json).
Usage: python3 tools/music.py  -> assets/music.wav
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parents[1] / "RISE_presentation" / "musique_Lyria.mp3"
SR = 48000
BEAT = 60 / 124
PHASE = 0.098  # the first beat
OPEN, BARS, LAST = 17, 5, 57  # the bar the reel opens on, how many bars it keeps, the track's last bar
TAIL = 2.02  # seconds kept from the last bar: its three beats and their ring
XFADE = 0.02


def main():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "m.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-ar", str(SR), "-ac", "2", str(wav)], check=True)
        x, _ = sf.read(wav, always_2d=True)
    at = lambda bar: int(round((PHASE + bar * 4 * BEAT) * SR))
    f = int(XFADE * SR)
    a = x[at(OPEN): at(OPEN + BARS) + f].copy()
    b = x[at(LAST): at(LAST) + int(TAIL * SR)].copy()
    ramp = np.sin(np.linspace(0, np.pi / 2, f))[:, None]  # equal-power join on the bar line
    joint = a[-f:] * ramp[::-1] + b[:f] * ramp
    y = np.concatenate([a[:-f], joint, b[f:]])
    n = int(0.25 * SR)
    y[-n:] *= np.cos(np.linspace(0, np.pi / 2, n))[:, None]
    y[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))[:, None]
    peak = np.max(np.abs(y))
    y = y / peak * 0.89
    sf.write(ROOT / "assets" / "music.wav", y, SR)
    print(f"music: {len(y) / SR:.3f}s, groove from {4 * BEAT:.3f}s, last bar from {BARS * 4 * BEAT:.3f}s")


if __name__ == "__main__":
    main()
