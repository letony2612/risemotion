"""The reel's sound: the reference reel's own audio, sent by the user (music/son_reel_reference.mp3, 9.33 s).

It is a run of whooshes that speed up, from one every 0.66 s to one every 0.26 s; the reference cuts at
the end of each one, and so does this reel (the cut times are in tools/build.py). Like the reference, the
reel loops at 9.5 s: the sound stops at 9.33 s and the empty beat at the end is silent.
The file is already at -14.2 LUFS (true peak -0.7 dB), so it is kept as it is, only padded with silence.
Usage: python3 tools/music.py  -> assets/music.wav
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "music" / "son_reel_reference.mp3"
SR = 48000
LOOP = 9.5


def main():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "m.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-ar", str(SR), "-ac", "2", str(wav)], check=True)
        x, _ = sf.read(wav, always_2d=True)
    n = int(round(LOOP * SR))
    y = np.zeros((n, 2))
    y[: min(n, len(x))] = x[:n]
    sf.write(ROOT / "assets" / "music.wav", y, SR)
    print(f"music: {len(x) / SR:.3f}s of sound, padded to {LOOP}s")


if __name__ == "__main__":
    main()
