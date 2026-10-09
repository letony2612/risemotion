"""Effects for the Apple-style cut (build.py --apple), from sounds generated with ElevenLabs Sound Effects.

The raw takes are in RISE_presentation/6_sons_apple/ (original sounds made for this video, not Apple's own).
Three soft, natural sounds only (bright clicks, ticks and swishes tired the ear): a muted fingertip tap
(two takes of it, from one file that holds two taps), a breath of air (the whoosh with its highs rolled
off), and a deep impact. Each is cut on its hit, faded at both ends and peak-normalized. The impact is
almost all sub (40-80 Hz), which a phone speaker cannot play: a soft saturation gives it a few harmonics
an octave or two up, so it is heard everywhere.
Usage: python3 tools/prepare_sfx_apple.py  -> assets/sfx_apple/<name>.wav
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import HighpassFilter, LowpassFilter, PeakFilter, Pedalboard

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT.parents[1] / "RISE_presentation" / "6_sons_apple"
OUT = ROOT / "assets" / "sfx_apple"
HOP = int(0.005 * SR)


def load(name):
    with tempfile.TemporaryDirectory() as d:
        w = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(RAW / f"{name}.mp3"), "-ar", str(SR), "-ac", "2", str(w)], check=True)
        x, _ = sf.read(w, always_2d=True)
    return x - x.mean(axis=0)


def envelope(x):
    m = x.mean(axis=1)
    return 20 * np.log10(np.array([np.sqrt(np.mean(m[i:i + HOP] ** 2)) for i in range(0, len(m) - HOP, HOP)]) + 1e-9)


def hits(x, floor=30, gap=0.02):
    """(start, end) in seconds of each hit: where the envelope is within `floor` dB of the loudest one."""
    db = envelope(x)
    on = db > db.max() - floor
    out, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or on[j:j + int(gap / 0.005)].any()):
                j += 1
            out.append((i * 0.005, j * 0.005, float(db[i:j].max())))
            i = j
        else:
            i += 1
    return out


def cut(x, a, b, pre=0.004, fade=0.04):
    y = x[max(0, int((a - pre) * SR)): int(b * SR)].copy()
    n_in, n_out = int(0.002 * SR), min(int(fade * SR), len(y) // 2)
    y[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    y[-n_out:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n_out)))[:, None]
    return y


def norm(x, peak=0.89):
    return x / (np.max(np.abs(x)) or 1) * peak


def board(x, *fx):
    return Pedalboard(list(fx))(x.T.astype(np.float32), SR).T.astype(np.float64)


def save(name, y):
    sf.write(OUT / f"{name}.wav", norm(y), SR)
    print(f"{name:7s} {len(y) / SR:.3f}s")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.wav"):
        old.unlink()
    # the fingertip tap: the take holds a faint tap then a clear one; both, cut on their hits
    tp = load("tap_soft")
    h = hits(tp, floor=30)
    save("tap", board(cut(tp, h[-1][0], h[-1][1] + 0.08, fade=0.06), LowpassFilter(4000)))
    save("tap2", board(cut(tp, h[0][0], min(h[0][1] + 0.06, h[-1][0] - 0.01), fade=0.04), LowpassFilter(4000)))
    # a breath of air: the whoosh, its highs rolled off, its lowest rumble too
    save("air", board(cut(load("whoosh"), 0, 0.85, fade=0.3), HighpassFilter(90), LowpassFilter(2500), LowpassFilter(2500)))
    # the impact: the long rumble shortened; its sub, saturated on its own, adds harmonics at 200-800 Hz
    # (the ear hears the boom's pitch from them on a phone speaker) that die away within half a second,
    # so the voice is clear again right after the hit; a little warmth at 110 Hz, no highs
    im = cut(load("impact"), 0, 1.7, fade=0.7)
    im = board(norm(im), HighpassFilter(28))
    harm = board(np.tanh(board(im, LowpassFilter(150)) * 6.0), HighpassFilter(180), HighpassFilter(180), LowpassFilter(1000))
    harm *= 0.6 * np.exp(-np.arange(len(harm)) / SR / 0.22)[:, None]
    save("impact", board(im + harm, PeakFilter(110, 3.0, 1.0)))


if __name__ == "__main__":
    main()
