"""Effects for the Apple-style cut (build.py --apple), from the sounds generated with ElevenLabs Sound Effects.

The raw takes are in RISE_presentation/6_sons_apple/ (original sounds made for this video, not Apple's own).
Some takes hold several hits (three ticks, four pops): each hit is cut out on its own, faded at both ends
and peak-normalized. The impact is almost all sub (40-80 Hz), which a phone speaker cannot play: a soft
saturation gives it harmonics an octave or two up, so it is heard everywhere.
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
    # a crisp tap; its two channels are unrelated noise, so one channel, centred
    tap = load("tap")
    ch = int(np.argmax(np.abs(tap).max(axis=0)))
    save("tap", cut(np.repeat(tap[:, ch:ch + 1], 2, axis=1), 0, 0.2, fade=0.08))
    # three ticks in the take: the loudest is the tick, the one before it a softer variant
    tk = load("tick")
    h = sorted(hits(tk, floor=24), key=lambda s: s[2])
    save("tick", cut(tk, h[-1][0], h[-1][1] + 0.03, fade=0.025))
    save("tick2", cut(tk, h[-2][0], h[-2][1] + 0.03, fade=0.025))
    # four bubble pops: one per sound, in the take's order
    pp = load("pop")
    h = hits(pp, floor=30)[:4]
    for i, (a, b, _) in enumerate(h):
        stop = min(b + 0.02, h[i + 1][0] - 0.006) if i + 1 < len(h) else b + 0.02  # not into the next pop
        save("pop" if i == 0 else f"pop{i + 1}", cut(pp, a, stop, fade=0.02))
    # the swish and the whoosh, without their silent tails
    save("swish", cut(load("swish"), 0, 0.42, fade=0.15))
    save("whoosh", cut(load("whoosh"), 0, 0.85, fade=0.3))
    # the impact: the long rumble shortened; its sub, saturated on its own, adds harmonics at 200-800 Hz
    # (the ear hears the boom's pitch from them on a phone speaker) that die away within half a second,
    # so the voice is clear again right after the hit; a little warmth at 110 Hz
    im = cut(load("impact"), 0, 1.7, fade=0.7)
    im = board(norm(im), HighpassFilter(28))
    harm = board(np.tanh(board(im, LowpassFilter(150)) * 6.0), HighpassFilter(180), HighpassFilter(180), LowpassFilter(1500))
    harm *= np.exp(-np.arange(len(harm)) / SR / 0.22)[:, None]
    save("impact", board(im + harm, PeakFilter(110, 3.0, 1.0)))


if __name__ == "__main__":
    main()
