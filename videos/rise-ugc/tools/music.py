"""The reel's sound: the RISE track (videos/rise-presentation/assets/audio/music_track.mp3, made with Lyria for
RISE) from its drop, so the very first frame is already full energy, and cut to silence on the beat where the end
card starts (40 ms fade, no click). Then, in the silence, the heavy boom when the logo's letters burst out
(music/boom.wav, made by videos/rise-mots/tools/boom.py). The music is brought to -14 LUFS, TikTok's loudness.
Usage: python3 tools/music.py  -> assets/music.wav
"""
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from build import BOOM_AT, DROP, DURATION, END_T0, ROOT

SRC = ROOT.parent / "rise-presentation" / "assets" / "audio" / "music_track.mp3"
SR = 48000
TARGET, BOOM_GAIN = -14.0, 0.85


def lufs(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])


def main():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "m.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{DROP - 0.01:.3f}", "-t", f"{END_T0:.3f}", "-i", str(SRC),
                        "-ar", str(SR), "-ac", "2", str(wav)], check=True)
        gain = 10 ** ((TARGET - lufs(wav)) / 20)
        x, _ = sf.read(wav, always_2d=True)
    n_end = int(round(END_T0 * SR))
    x = x[:n_end] * gain
    fade = int(0.04 * SR)
    x[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade))[:, None]
    y = np.zeros((int(round(DURATION * SR)), 2))
    y[: len(x)] = x
    boom, _ = sf.read(ROOT / "music" / "boom.wav", always_2d=True)
    at = int(round(BOOM_AT * SR))
    k = min(len(boom), len(y) - at)
    y[at: at + k] += BOOM_GAIN * boom[:k]
    peak = np.max(np.abs(y))
    if peak > 0.94:  # keep a little headroom for the AAC encoder
        y *= 0.94 / peak
    sf.write(ROOT / "assets" / "music.wav", y, SR)
    print(f"music: {END_T0:.3f}s of the track from {DROP:.3f}s (gain {20 * np.log10(gain):+.1f} dB), the boom at {BOOM_AT:.3f}s, "
          f"{DURATION}s in all, peak {20 * np.log10(np.max(np.abs(y))):.1f} dBFS, {lufs(ROOT / 'assets' / 'music.wav'):.1f} LUFS")


if __name__ == "__main__":
    main()
