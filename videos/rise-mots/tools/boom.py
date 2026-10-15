"""The heavy boom under the logo: synthesized here, so it is ours and the same on every run.

A sine that drops from 160 Hz to 52 Hz (the weight), a short 110 Hz hit and a thump of filtered noise
(the punch and the body a phone speaker can play: it plays nothing under ~100 Hz), a short bright crack,
all driven into a soft clipper that adds harmonics, then a dark stereo reverb tail. About 3 s long.
Usage: python3 tools/boom.py  -> music/boom.wav (tools/music.py mixes it in under the logo)
"""
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 48000
LENGTH = 3.0


def band(x, lo=None, hi=None, order=4):
    if lo and hi:
        sos = butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    elif lo:
        sos = butter(order, lo, "highpass", fs=SR, output="sos")
    else:
        sos = butter(order, hi, "lowpass", fs=SR, output="sos")
    return sosfilt(sos, x)


def main():
    rng = np.random.default_rng(1015)
    n = int(LENGTH * SR)
    t = np.arange(n) / SR
    attack = 1 - np.exp(-t / 0.0015)
    # the weight: a sine whose pitch falls fast from 160 Hz to 52 Hz
    f = 52 + (160 - 52) * np.exp(-t / 0.06)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55) * attack
    # the punch a phone can play: a short 110 Hz hit
    punch = np.sin(2 * np.pi * np.cumsum(110 + 70 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.11) * attack
    # the body: low noise, short
    body = band(rng.standard_normal(n), lo=60, hi=600) * np.exp(-t / 0.16) * attack
    body /= np.max(np.abs(body))
    # the crack: a few ms of bright noise
    crack = band(rng.standard_normal(n), lo=1200, hi=7000) * np.exp(-t / 0.014) * attack
    crack /= np.max(np.abs(crack))
    dry = 0.85 * sub + 0.7 * punch + 0.55 * body + 0.3 * crack
    dry = np.tanh(2.6 * dry) / np.tanh(2.6)  # soft clip: more harmonics for small speakers
    dry = band(dry, lo=32, order=2)  # nothing under what any speaker plays
    # a dark stereo tail, under the hit rather than after it
    ir_n = int(2.2 * SR)
    ti = np.arange(ir_n) / SR
    tails = []
    for seed in (7, 8):
        ir = np.random.default_rng(seed).standard_normal(ir_n) * np.exp(-ti / 0.5) * (1 - np.exp(-ti / 0.03))
        ir = band(ir, lo=60, hi=1500)
        ir /= np.sqrt(np.sum(ir ** 2))
        tails.append(fftconvolve(dry, ir)[:n])
    wet = np.stack(tails, 1)
    y = dry[:, None] + wet * 0.22
    fade = int(0.6 * SR)
    y[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade))[:, None]
    y = y / np.max(np.abs(y)) * 0.89
    (ROOT / "music").mkdir(exist_ok=True)
    sf.write(ROOT / "music" / "boom.wav", y, SR)
    print(f"boom: {LENGTH}s, peak {20 * np.log10(np.max(np.abs(y))):.1f} dBFS")


if __name__ == "__main__":
    main()
