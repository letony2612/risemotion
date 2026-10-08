"""Original music bed for the RISE video (no samples, fully synthesized).

120 BPM, D major, I-V-vi-IV, one chord per bar (2 s). Sections follow the edit:
  0-4    intro: pad + soft arpeggio, chime when the logo appears (2.5 s)
  4-24   groove: kick, claps, hats, bass, plucks
  24-27.5 "morning" break: filtered, riser into the quiz
  27.5-34 lift: full groove + lead
  34-end outro: final chord rings out
Usage: python3 tools/compose_music.py assets/music/rise_bed.wav
"""
import sys
import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, Reverb, Compressor, LowpassFilter, HighpassFilter, Limiter, Chorus

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
LENGTH = 40.0
N = int(LENGTH * SR)
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# D, A, Bm, G  (root midi, chord tones)
CHORDS = [
    (50, [62, 66, 69, 74]),  # D
    (45, [61, 64, 69, 73]),  # A
    (47, [62, 66, 71, 74]),  # Bm
    (43, [62, 67, 71, 74]),  # G
]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


def env_adsr(n, a, d, s, r, sustain_len):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    hold = max(0, int(sustain_len * SR) - a - d)
    e = np.concatenate([
        np.linspace(0, 1, max(a, 1), endpoint=False),
        np.linspace(1, s, max(d, 1), endpoint=False),
        np.full(hold, s),
        np.linspace(s, 0, max(r, 1)),
    ])
    out = np.zeros(n)
    out[: min(n, len(e))] = e[:n]
    return out


def saw(freq, t, phase=0.0):
    x = (freq * t + phase) % 1.0
    return 2 * x - 1


def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


L = np.zeros(N)
Rr = np.zeros(N)
pad_l, pad_r = np.zeros(N), np.zeros(N)
pluck = np.zeros(N)
bass = np.zeros(N)
drums = np.zeros(N)
hats = np.zeros(N)
fx = np.zeros(N)
lead = np.zeros(N)

# ---------------- pad (supersaw, per bar) ----------------
for bar in range(int(LENGTH // BAR) + 1):
    t0 = bar * BAR
    if t0 >= 38.0:
        break
    root, tones = chord_at(t0)
    dur = BAR + 0.6
    if t0 >= 34.0:  # final chord holds to the end
        root, tones = CHORDS[0]
        dur = LENGTH - t0
    n = int(dur * SR)
    t = np.arange(n) / SR
    sl, sr_ = np.zeros(n), np.zeros(n)
    for note in tones:
        f = midi(note)
        for k, det in enumerate([-0.12, -0.06, 0.0, 0.06, 0.12]):
            ph = rng.random()
            v = saw(f * 2 ** (det / 12), t, ph)
            if k % 2:
                sl += v
            else:
                sr_ += v
    e = env_adsr(n, 0.35, 0.3, 0.8, 0.7, dur - 0.7)
    add(pad_l, t0, sl * e)
    add(pad_r, t0, sr_ * e)

# ---------------- plucks (16th arpeggio) ----------------
def pluck_note(f, dur=0.32, bright=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = saw(f, t) * 0.6 + np.sin(2 * np.pi * f * t) * 0.4 + np.sin(2 * np.pi * 2 * f * t) * 0.15 * bright
    return tone * np.exp(-t * 11)


ARP = [0, 1, 2, 3, 2, 1, 3, 2]
for i in range(int(LENGTH / (BEAT / 4))):
    t0 = i * BEAT / 4
    if t0 >= 34.0:
        break
    if t0 < 1.0:
        continue
    _, tones = chord_at(t0)
    step = i % 8
    note = tones[ARP[step]] + 12
    vel = 0.55 if t0 < 4 else (0.8 if step % 2 == 0 else 0.55)
    if 24.0 <= t0 < 27.5:
        vel *= 0.6
    add(pluck, t0, pluck_note(midi(note)) * vel)

# ---------------- bass (8ths, sidechained later) ----------------
for i in range(int(LENGTH / (BEAT / 2))):
    t0 = i * BEAT / 2
    if t0 < 4.0 or t0 >= 34.0 or (24.0 <= t0 < 27.5):
        continue
    root, _ = chord_at(t0)
    f = midi(root - 12 + 12)
    n = int(0.24 * SR)
    t = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * t) + 0.25 * saw(f, t)
    v *= env_adsr(n, 0.005, 0.08, 0.7, 0.06, 0.18)
    add(bass, t0, v * (0.9 if i % 2 == 0 else 0.7))

# ---------------- drums ----------------
def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) + 0.15 * np.exp(-t * 200) * rng.standard_normal(n)


def clap():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    e = np.zeros(n)
    for off in (0.0, 0.011, 0.022):
        e += np.exp(-np.clip(t - off, 0, None) * 60) * (t >= off)
    e += 0.6 * np.exp(-t * 18)
    return noise * e * 0.5


def hat(open_=False):
    n = int((0.12 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    return rng.standard_normal(n) * np.exp(-t * (25 if open_ else 90))


kick_times = []
for i in range(int(LENGTH / BEAT)):
    t0 = i * BEAT
    in_groove = 4.0 <= t0 < 24.0 or 27.5 <= t0 < 34.0
    if in_groove:
        add(drums, t0, kick() * 0.95)
        kick_times.append(t0)
        if i % 2 == 1:
            add(drums, t0, clap() * (0.55 if t0 < 27.5 else 0.7))
        add(hats, t0 + BEAT / 2, hat(open_=(t0 >= 27.5)) * 0.35)
        if t0 >= 17.5:
            add(hats, t0 + BEAT / 4, hat() * 0.15)
            add(hats, t0 + 3 * BEAT / 4, hat() * 0.15)
# break: soft kick on 1 only
for t0 in (24.0, 26.0):
    add(drums, t0, kick() * 0.5)
    kick_times.append(t0)
# snare roll into the lift
roll_start = 26.5
k = 0
while roll_start + k * (BEAT / 4) < 27.5:
    t0 = roll_start + k * (BEAT / 4)
    add(drums, t0, clap() * (0.15 + 0.4 * k / 8))
    k += 1
# final hit
add(drums, 34.0, kick() * 0.9)
kick_times.append(34.0)

# ---------------- fx: chimes + risers ----------------
def chime(f, dur=2.5, amp=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    v = sum(np.sin(2 * np.pi * f * m * t) * a for m, a in ((1, 1), (2.01, 0.4), (3.98, 0.15)))
    return v * np.exp(-t * 2.2) * amp


add(fx, 2.5, chime(midi(86)) + chime(midi(90), amp=0.3))  # logo
add(fx, 15.0, chime(midi(93), amp=0.35))  # prayer answered
add(fx, 33.2, chime(midi(98), amp=0.25))  # "Exact !"
add(fx, 34.2, chime(midi(86), 4.5, 0.5) + chime(midi(93), 4.5, 0.3))  # end card


def riser(start, dur, amp=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    sig = np.zeros(n)
    # sweep a simple one-pole lowpass upward
    y = 0.0
    for i in range(n):
        a = 0.02 + 0.5 * (t[i] / dur) ** 2
        y += a * (noise[i] - y)
        sig[i] = y
    sig *= (t / dur) ** 2 * amp
    add(fx, start, sig)


riser(2.0, 2.0, 0.25)
riser(25.5, 2.0, 0.45)
riser(32.5, 1.5, 0.2)

# ---------------- lead (lift section only) ----------------
MEL = [74, 76, 78, 81, 78, 76, 74, 73]
for i, t0 in enumerate(np.arange(27.5, 33.5, BEAT)):
    note = MEL[i % len(MEL)]
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = midi(note)
    v = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * saw(f, t)) * env_adsr(n, 0.01, 0.15, 0.5, 0.2, 0.3)
    add(lead, t0, v * 0.35)

# ---------------- sidechain envelope ----------------
side = np.ones(N)
for t0 in kick_times:
    i = int(t0 * SR)
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    duck = 1 - 0.6 * np.exp(-t * 9)
    j = min(N, i + n)
    side[i:j] = np.minimum(side[i:j], duck[: j - i])


def norm(x, peak):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def proc(x, board):
    return board(x.astype(np.float32)[None, :], SR)[0]


# section-dependent pad filtering: darker during intro and the morning break
pad_l = norm(pad_l, 1) * side
pad_r = norm(pad_r, 1) * side
pad_board = Pedalboard([HighpassFilter(150), LowpassFilter(3200), Chorus(rate_hz=0.3, depth=0.3, mix=0.4), Reverb(room_size=0.8, wet_level=0.35, dry_level=0.7)])
pad_l = proc(pad_l, pad_board)
pad_r = proc(pad_r, pad_board)
dark = Pedalboard([LowpassFilter(900)])
pad_dark_l, pad_dark_r = proc(pad_l, dark), proc(pad_r, dark)
mixw = np.ones(N)
tt = np.arange(N) / SR
mixw = np.clip(np.interp(tt, [0, 3.5, 4.0, 23.5, 24.0, 27.0, 27.5, 40], [0, 0.2, 1, 1, 0.1, 0.5, 1, 1]), 0, 1)
pad_l = pad_l * mixw + pad_dark_l * (1 - mixw)
pad_r = pad_r * mixw + pad_dark_r * (1 - mixw)

pluck = proc(norm(pluck, 1), Pedalboard([HighpassFilter(250), LowpassFilter(5500), Reverb(room_size=0.55, wet_level=0.3, dry_level=0.8)]))
bass = proc(norm(bass, 1) * side, Pedalboard([LowpassFilter(700)]))
drums = proc(norm(drums, 1), Pedalboard([Compressor(threshold_db=-12, ratio=3), Reverb(room_size=0.25, wet_level=0.08, dry_level=1)]))
hats = proc(norm(hats, 1), Pedalboard([HighpassFilter(7000)]))
fx = proc(norm(fx, 1), Pedalboard([Reverb(room_size=0.9, wet_level=0.45, dry_level=0.7)]))
lead = proc(norm(lead, 1), Pedalboard([LowpassFilter(6000), Reverb(room_size=0.7, wet_level=0.35, dry_level=0.8)]))

# stereo placement
pl = norm(pluck, 1)
L = 0.30 * pad_l + 0.20 * pl * 1.0 + 0.32 * bass + 0.55 * drums + 0.16 * hats * 0.7 + 0.30 * fx + 0.22 * lead * 0.8
Rr = 0.30 * pad_r + 0.20 * np.roll(pl, int(0.012 * SR)) + 0.32 * bass + 0.55 * drums + 0.16 * hats * 1.0 + 0.30 * fx + 0.22 * lead
# fades
fade = np.interp(tt, [0, 0.4, 37.5, 39.8, 40], [0, 1, 1, 0, 0])
L *= fade
Rr *= fade

master = np.stack([L, Rr]).astype(np.float32)
master = Pedalboard([HighpassFilter(30), Compressor(threshold_db=-14, ratio=2.5, attack_ms=10, release_ms=120), Limiter(threshold_db=-1.0)])(master, SR)
master = master / np.max(np.abs(master)) * 0.89
sf.write(sys.argv[1], master.T, SR)
print("wrote", sys.argv[1], master.shape[1] / SR, "s")
