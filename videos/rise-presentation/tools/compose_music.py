"""Original music bed for the RISE video, synthesized and locked to tools/timeline.py.

120 BPM, D major (I-V-vi-IV). If assets/audio/music_source.wav exists (a licensed
or generated track) it is used instead, trimmed/faded to the video length.
Usage: python3 tools/compose_music.py -> assets/audio/music.wav
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, Reverb, Compressor, LowpassFilter, HighpassFilter, Limiter, Chorus, Delay, Gain

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402

SR = 44100
ROOT = T.ROOT
OUT = ROOT / "assets" / "audio" / f"music{T.SUFFIX}.wav"
BEAT = 60 / T.BPM
BAR = 4 * BEAT
L = T.DURATION + 1.0
N = int(L * SR)
rng = np.random.default_rng(21)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


CHORDS = [(50, [62, 66, 69, 74]), (45, [61, 64, 69, 73]), (47, [62, 66, 71, 74]), (43, [62, 67, 71, 74])]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


def blep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    out[m] = x + x - x * x - 1
    m2 = t > 1 - dt
    x = (t[m2] - 1) / dt[m2]
    out[m2] = x * x + x + x + 1
    return out


def saw(freq, n, phase=0.0):
    dt = np.full(n, freq / SR)
    ph = (phase + np.cumsum(dt)) % 1.0
    return 2 * ph - 1 - blep(ph, dt)


def adsr(n, a, d, s, r):
    a, d, r = max(1, int(a * SR)), max(1, int(d * SR)), max(1, int(r * SR))
    sus = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, a), np.linspace(1, s, d), np.full(sus, s), np.linspace(s, 0, r)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def put(buf, t, sig, gain=1.0):
    i = int(t * SR)
    if i >= len(buf) or i < 0:
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def proc(x, board):
    return board(np.asarray(x, dtype=np.float32)[None, :] if x.ndim == 1 else x.T.astype(np.float32), SR)


def mono(x, board):
    return board(np.asarray(x, dtype=np.float32)[None, :], SR)[0]


# ------------------------------------------------------------------ instruments
def kick():
    t = np.arange(int(0.42 * SR)) / SR
    f = 46 + 130 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.35
    return np.tanh((body + click) * 1.6) * 0.9


def clap():
    t = np.arange(int(0.3 * SR)) / SR
    n = rng.standard_normal(len(t))
    e = sum(np.exp(-np.clip(t - o, 0, None) * 70) * (t >= o) for o in (0, 0.012, 0.024)) + 0.7 * np.exp(-t * 16)
    tone = np.sin(2 * np.pi * 210 * t) * np.exp(-t * 30) * 0.4
    return mono(n * e * 0.45 + tone, Pedalboard([HighpassFilter(700), LowpassFilter(7000)]))


def hat(open_=False):
    t = np.arange(int((0.18 if open_ else 0.05) * SR)) / SR
    return mono(rng.standard_normal(len(t)) * np.exp(-t * (18 if open_ else 95)), Pedalboard([HighpassFilter(7500)]))


def crash(dur=2.5):
    t = np.arange(int(dur * SR)) / SR
    return mono(rng.standard_normal(len(t)) * np.exp(-t * 1.6) * 0.6, Pedalboard([HighpassFilter(4500)]))


def riser(dur):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    y, out = 0.0, np.zeros(n)
    for i in range(n):  # sweeping one-pole lowpass
        a = 0.01 + 0.6 * t[i] ** 2
        y += a * (noise[i] - y)
        out[i] = y
    tone = saw(110 * 2 ** (t * 3), n) * 0.12
    return (out * 2 + tone) * t ** 2.2


def supersaw(notes, dur, detune=0.14, voices=5):
    n = int(dur * SR)
    l, r = np.zeros(n), np.zeros(n)
    for note in notes:
        f = midi(note)
        for k in range(voices):
            d = (k - (voices - 1) / 2) / ((voices - 1) / 2) * detune
            v = saw(f * 2 ** (d / 12), n, rng.random())
            if k % 2:
                l += v
            else:
                r += v
    return l, r


# ------------------------------------------------------------------ arrangement
E = T.events(T.words())
land, stamp, drop, end = E["logo_land"], E["stamp"], T.S["quiz"], T.S["end"]
groove_a = (E["share"], E["verse"])
breakdown = (24.0, drop)
drop_sec = (drop, end)

kick_buf, clap_buf, hat_buf, perc_fx = (np.zeros(N) for _ in range(4))
bass = np.zeros(N)
padL, padR = np.zeros(N), np.zeros(N)
stabL, stabR = np.zeros(N), np.zeros(N)
pluck = np.zeros(N)
lead = np.zeros(N)
fx = np.zeros(N)
kick_times = []

K, C = kick(), clap()
HC, HO = hat(), hat(True)
for i in range(int(L / BEAT)):
    t = i * BEAT
    in_a = groove_a[0] <= t < groove_a[1] and not (stamp - 0.5 <= t < stamp)
    in_drop = drop_sec[0] <= t < drop_sec[1] - 0.01
    if in_a or in_drop:
        put(kick_buf, t, K)
        kick_times.append(t)
        if i % 2 == 1:
            put(clap_buf, t, C, 0.85 if in_drop else 0.7)
        put(hat_buf, t + BEAT / 2, HO if (in_drop or t >= E["groups"]) else HC, 0.5 if in_drop else 0.38)
        if t >= E["groups"] or in_drop:
            put(hat_buf, t + BEAT / 4, HC, 0.18)
            put(hat_buf, t + 3 * BEAT / 4, HC, 0.18)
# fills (snare rolls) into section changes
for t0, t1 in ((E["share"] - 0.5, E["share"]), (E["pray"] - 0.5, E["pray"]), (E["groups"] - 0.5, E["groups"]),
               (drop - 1.0, drop - 0.25), (end - 0.5, end)):
    steps = int((t1 - t0) / (BEAT / 4))
    for k in range(steps):
        put(clap_buf, t0 + k * BEAT / 4, C, 0.2 + 0.5 * k / max(1, steps - 1))
# hits
for t in (land, stamp, drop, end):
    put(kick_buf, t, K, 1.0)
    kick_times.append(t)
    put(fx, t, crash(2.8), 0.7)
for t0, t1 in ((1.2, land), (stamp - 0.9, stamp), (drop - 2.4, drop - 0.22), (end - 1.6, end)):
    put(fx, t0, riser(t1 - t0), 0.5)

# bass: 8ths in groove, octave bounce in the drop
for i in range(int(L / (BEAT / 2))):
    t = i * BEAT / 2
    in_a = groove_a[0] <= t < groove_a[1] and not (stamp - 0.5 <= t < stamp)
    in_drop = drop_sec[0] <= t < drop_sec[1]
    if not (in_a or in_drop):
        continue
    root, _ = chord_at(t)
    note = root - 12 + (12 if (in_drop and i % 2) else 0)
    n = int(0.23 * SR)
    f = midi(note)
    tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * tt) * 0.9 + saw(f, n) * 0.35
    put(bass, t, v * adsr(n, 0.004, 0.06, 0.75, 0.05), 0.95 if i % 2 == 0 else 0.8)

# pads: whole film, darker in the intro / breakdown
for b in range(int(L // BAR) + 1):
    t0 = b * BAR
    if t0 >= end:
        break
    _, tones = chord_at(t0)
    l, r = supersaw(tones, BAR + 0.5, 0.12, 5)
    e = adsr(len(l), 0.25, 0.4, 0.75, 0.5)
    put(padL, t0, l * e)
    put(padR, t0, r * e)
l, r = supersaw([62, 66, 69, 74, 78], L - end, 0.12, 5)
e = adsr(len(l), 0.05, 0.8, 0.6, 3.5)
put(padL, end, l * e)
put(padR, end, r * e)

# chord stabs: syncopated house rhythm in the groove and the drop
STAB = [0, 0.75, 1.5, 2.5, 3.0]
for b in range(int(L // BAR) + 1):
    t0 = b * BAR
    for s in STAB:
        t = t0 + s * BEAT
        in_a = groove_a[0] + 2 <= t < groove_a[1] and not (stamp - 0.5 <= t < stamp)
        in_drop = drop_sec[0] <= t < drop_sec[1]
        if not (in_a or in_drop):
            continue
        _, tones = chord_at(t)
        l, r = supersaw([x + 12 for x in tones], 0.28, 0.18, 5)
        e = adsr(len(l), 0.003, 0.12, 0.25, 0.08)
        g = 0.8 if in_drop else 0.45
        put(stabL, t, l * e * g)
        put(stabR, t, r * e * g)

# plucked arpeggio (16ths): intro, groove (softer), breakdown
ARP = [0, 1, 2, 3, 2, 1, 3, 2]
for i in range(int(L / (BEAT / 4))):
    t = i * BEAT / 4
    if t < 0.4 or t >= end:
        continue
    _, tones = chord_at(t)
    note = tones[ARP[i % 8]] + 12
    n = int(0.3 * SR)
    tt = np.arange(n) / SR
    v = (saw(midi(note), n) * 0.5 + np.sin(2 * np.pi * midi(note) * tt) * 0.5) * np.exp(-tt * 13)
    g = 0.5 if t < 4 else (0.32 if t < 24 else (0.55 if t < drop else 0.25))
    put(pluck, t, v, g)

# lead hook in the drop
MEL = [(0, 78, 1), (1, 76, 0.5), (1.5, 74, 0.5), (2, 76, 1), (3, 81, 1), (4, 78, 1), (5, 76, 0.5), (5.5, 74, 0.5),
       (6, 73, 1), (7, 74, 1), (8, 78, 1), (9, 76, 0.5), (9.5, 74, 0.5), (10, 76, 1), (11, 83, 1)]
for beat, note, length in MEL:
    t = drop + beat * BEAT
    if t >= end:
        break
    n = int(length * BEAT * SR)
    tt = np.arange(n) / SR
    f = midi(note)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * tt) * (tt > 0.15)
    v = saw(f, n) * 0.4 + saw(f * 1.003, n) * 0.4 + np.sin(2 * np.pi * f * vib * tt) * 0.4
    put(lead, t, v * adsr(n, 0.01, 0.1, 0.7, 0.08), 0.6)

# bells at the end
for k, note in enumerate([86, 90, 93, 98]):
    tt = np.arange(int(3 * SR)) / SR
    f = midi(note)
    put(fx, end + 0.15 + k * 0.25, (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt * 1.8), 0.22)

# ------------------------------------------------------------------ mix
side = np.ones(N)
for t in kick_times:
    i, n = int(t * SR), int(0.4 * SR)
    tt = np.arange(n) / SR
    j = min(N, i + n)
    side[i:j] = np.minimum(side[i:j], (1 - 0.65 * np.exp(-tt * 10))[: j - i])

tt = np.arange(N) / SR
bright = np.interp(tt, [0, land, E["share"], E["verse"] - 0.4, E["verse"] + 0.2, drop - 1.0, drop - 0.25, drop, end, L],
                   [0.15, 0.4, 1, 1, 0.25, 0.55, 0.0, 1, 1, 0.6])
gap = np.interp(tt, [drop - 0.3, drop - 0.26, drop - 0.03, drop], [1, 0, 0, 1])  # breath before the drop


def norm(x):
    return x / (np.max(np.abs(x)) or 1)


def filt_mix(x, lo, hi):
    dark = mono(x, Pedalboard([LowpassFilter(lo)]))
    light = mono(x, Pedalboard([LowpassFilter(hi)]))
    return dark * (1 - bright) + light * bright


padL = filt_mix(norm(padL) * side, 700, 4200)
padR = filt_mix(norm(padR) * side, 700, 4200)
pad = proc(np.stack([padL, padR], 1), Pedalboard([HighpassFilter(140), Chorus(rate_hz=0.25, depth=0.3, mix=0.35), Reverb(room_size=0.82, wet_level=0.3, dry_level=0.8)])).T
stab = proc(np.stack([norm(stabL), norm(stabR)], 1) * side[:, None], Pedalboard([HighpassFilter(250), LowpassFilter(6500), Reverb(room_size=0.5, wet_level=0.18, dry_level=0.9)])).T
pl = mono(norm(pluck), Pedalboard([HighpassFilter(300), LowpassFilter(6000), Delay(delay_seconds=BEAT * 0.75, feedback=0.28, mix=0.22), Reverb(room_size=0.6, wet_level=0.25, dry_level=0.85)]))
bs = mono(norm(bass) * side, Pedalboard([LowpassFilter(900), Compressor(threshold_db=-12, ratio=4)]))
kk = mono(norm(kick_buf), Pedalboard([Compressor(threshold_db=-8, ratio=3, attack_ms=3, release_ms=60)]))
cl = mono(norm(clap_buf), Pedalboard([Reverb(room_size=0.45, wet_level=0.22, dry_level=0.9)]))
hh = norm(hat_buf)
ld = mono(norm(lead), Pedalboard([HighpassFilter(250), LowpassFilter(7000), Delay(delay_seconds=BEAT * 0.75, feedback=0.25, mix=0.2), Reverb(room_size=0.65, wet_level=0.3, dry_level=0.85)]))
fxm = mono(norm(fx), Pedalboard([Reverb(room_size=0.85, wet_level=0.35, dry_level=0.8)]))

Lm = 0.30 * pad[:, 0] + 0.20 * stab[:, 0] + 0.17 * pl + 0.36 * bs + 0.60 * kk + 0.26 * cl + 0.11 * hh + 0.20 * ld + 0.26 * fxm
Rm = 0.30 * pad[:, 1] + 0.20 * stab[:, 1] + 0.17 * np.roll(pl, int(0.011 * SR)) + 0.36 * bs + 0.60 * kk + 0.26 * cl + 0.13 * hh + 0.20 * ld + 0.26 * fxm
fade = np.interp(tt, [0, 0.3, T.DURATION - 1.6, T.DURATION], [0, 1, 1, 0])
master = np.stack([Lm * fade * gap, Rm * fade * gap], 0).astype(np.float32)
master = Pedalboard([HighpassFilter(28), Compressor(threshold_db=-16, ratio=2.5, attack_ms=12, release_ms=140), Gain(3), Limiter(threshold_db=-1.0)])(master, SR)
master = master[:, : int(T.DURATION * SR)]
master = master / np.max(np.abs(master)) * 0.89

from import_music import INFO, fit, load, track  # noqa: E402

track = track()
OUT.parent.mkdir(parents=True, exist_ok=True)


def ducked(y, depth_db=-5):
    """The bed dips while the voice speaks (on top of the spectral carve build.py adds)."""
    return y * (1 - (1 - 10 ** (depth_db / 20)) * T.voice_activity(y.shape[1], SR))


if track and INFO.exists():  # an imported track (tools/import_music.py), fitted to this edit
    sf.write(OUT, ducked(fit(load(track), json.loads(INFO.read_text()), drop, end, T.DURATION)).T, SR)
    print("music: using", track.name)
else:
    sf.write(OUT, ducked(master).T, SR)
    print("music: synthesized bed written", OUT.name)
