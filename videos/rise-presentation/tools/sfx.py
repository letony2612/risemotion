"""Sound design for the RISE video: a small synthesized SFX library + the cue renderer.

Every sound is synthesized here (no samples, nothing to license). Files in
assets/sfx/<name>.wav override the synthesized sound of the same name, so a
better recorded or generated effect can be dropped in without touching code.
Usage: python3 tools/sfx.py  -> writes assets/audio/sfx.wav from timeline.CUES
       python3 tools/sfx.py --apple  -> assets/audio/sfx_apple.wav: the Apple-style cue sheet, played with the
       sounds generated for it (assets/sfx_apple, made by prepare_sfx_apple.py); "<name>_rev" plays one backwards
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import istft, stft
from pedalboard import Pedalboard, Reverb, HighpassFilter, LowpassFilter, Compressor, Limiter

sys.path.insert(0, str(Path(__file__).parent))
import timeline  # noqa: E402

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
STYLE = "apple" if "--apple" in sys.argv else ""
SAMPLES = ROOT / "assets" / ("sfx_apple" if STYLE else "sfx")
rng = np.random.default_rng(11)


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, attack, release, curve=4.0):
    a = int(attack * SR)
    e = np.ones(n)
    if a:
        e[:a] = np.linspace(0, 1, a) ** 2
    r = n - a
    e[a:] = np.exp(-np.linspace(0, curve, r))
    return e


def band_sweep(noise, f_start, f_end, width=0.6, shape=None):
    """STFT-domain moving band-pass: the band centre glides from f_start to f_end."""
    f, tt, Z = stft(noise, SR, nperseg=1024, noverlap=768)
    frames = Z.shape[1]
    centers = np.geomspace(f_start, f_end, frames) if shape is None else shape(frames)
    logf = np.log(np.maximum(f, 20))[:, None]
    g = np.exp(-((logf - np.log(centers)[None, :]) ** 2) / (2 * width ** 2))
    _, y = istft(Z * g, SR, nperseg=1024, noverlap=768)
    return y[: len(noise)]


def stereo(x, pan=0.0):
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * l, x * r], axis=1)


def pan_sweep(x, p0, p1):
    p = np.linspace(p0, p1, len(x))
    return np.stack([x * np.cos((p + 1) * np.pi / 4), x * np.sin((p + 1) * np.pi / 4)], axis=1)


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def verb(x, room=0.5, wet=0.25):
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    b = Pedalboard([Reverb(room_size=room, wet_level=wet, dry_level=1.0, width=1.0)])
    tail = np.zeros((int(SR * room * 1.5), 2))
    y = b(np.vstack([x, tail]).T.astype(np.float32), SR).T
    return y


# ---------------------------------------------------------------- library
def whoosh(dur=0.55, f0=250, f1=4000, peak_at=0.6, pan=(-0.6, 0.6)):
    n = int(dur * SR)
    x = band_sweep(rng.standard_normal(n), f0, f1, 0.55)
    t = np.linspace(0, 1, n)
    e = np.where(t < peak_at, (t / peak_at) ** 2.2, ((1 - t) / (1 - peak_at)) ** 1.6)
    return verb(pan_sweep(norm(x * e), *pan), 0.35, 0.18)


def whoosh_up():
    return whoosh(0.6, 200, 6000, 0.72, (-0.2, 0.2))


def whoosh_fast():
    return whoosh(0.32, 600, 5000, 0.55, (0.8, -0.8))


def whoosh_long():
    return whoosh(1.1, 150, 7000, 0.8, (-0.7, 0.7))


def swish():
    return whoosh(0.2, 1500, 7000, 0.4, (-0.3, 0.3)) * 0.8


def suck():
    w = whoosh(0.45, 6000, 300, 0.85, (0.4, -0.4))
    return w


def pop(f=820):
    t = t_(0.14)
    freq = f * (1 + 1.6 * np.exp(-t * 55))
    ph = 2 * np.pi * np.cumsum(freq) / SR
    x = np.sin(ph) * np.exp(-t * 32)
    x[:30] += rng.standard_normal(30) * 0.25 * np.linspace(1, 0, 30)
    return verb(stereo(norm(x), 0), 0.2, 0.12)


def pop2():
    return pop(1040)


def pop3():
    return pop(1320)


def click():
    t = t_(0.06)
    x = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 140) * 0.6
    x[:90] += rng.standard_normal(90) * np.linspace(1, 0, 90)
    body = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 60) * 0.5
    return verb(stereo(norm(x + body), 0), 0.15, 0.08)


def tick():
    t = t_(0.03)
    x = np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 260)
    x[:40] += rng.standard_normal(40) * 0.4 * np.linspace(1, 0, 40)
    return stereo(norm(x, 0.7), 0.1)


def bell(f, dur=1.2, decay=3.5, amp=1.0):
    t = t_(dur)
    x = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * decay * (1 + m * 0.3))
            for m, a in ((1, 1.0), (2.0, 0.35), (2.76, 0.18), (5.4, 0.06)))
    x *= np.minimum(1, t / 0.004)
    return x * amp


def ding():
    a = bell(1318.5, 1.0, 4.0)
    b = bell(1975.5, 1.0, 4.0)
    out = np.zeros(int(1.1 * SR))
    out[: len(a)] += a
    o = int(0.09 * SR)
    out[o : o + len(b)] += b[: len(out) - o]
    return verb(stereo(norm(out, 0.8), 0.15), 0.4, 0.2)


def ding2():
    a = bell(1567.98, 1.0, 4.0)
    b = bell(2349.3, 1.0, 4.0)
    out = np.zeros(int(1.1 * SR))
    out[: len(a)] += a
    o = int(0.09 * SR)
    out[o : o + len(b)] += b[: len(out) - o]
    return verb(stereo(norm(out, 0.8), -0.15), 0.4, 0.2)


def msg_in():
    t = t_(0.18)
    f = np.where(t < 0.07, 740, 988)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-((t % 0.07) * 28)) * np.exp(-t * 6)
    return verb(stereo(norm(x, 0.8), -0.2), 0.2, 0.12)


def msg_out():
    t = t_(0.16)
    f = 520 + 900 * (t / 0.16) ** 0.7
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.16) ** 1.5
    w = band_sweep(rng.standard_normal(len(t)), 1500, 6000, 0.5) * np.sin(np.pi * t / 0.16) * 0.25
    return verb(stereo(norm(x + w, 0.8), 0.2), 0.2, 0.12)


def impact(big=True):
    dur = 2.2 if big else 1.3
    t = t_(dur)
    f = 32 + 95 * np.exp(-t * 7)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (2.2 if big else 3.5))
    noise = rng.standard_normal(len(t))
    thump = band_sweep(noise, 1800, 120, 0.8) * np.exp(-t * 9)
    crack = band_sweep(noise, 5000, 2500, 0.5) * np.exp(-t * 30) * 0.5
    x = sub * 1.0 + thump * 0.9 + crack
    x = Pedalboard([Compressor(threshold_db=-10, ratio=4, attack_ms=1, release_ms=80)])(
        x.astype(np.float32)[None, :], SR)[0]
    return verb(stereo(norm(x, 0.95), 0), 0.75, 0.3)


def impact_soft():
    return impact(False) * 0.6


def hit():
    t = t_(0.5)
    f = 48 + 120 * np.exp(-t * 26)
    k = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)
    snap = band_sweep(rng.standard_normal(len(t)), 3500, 2000, 0.6) * np.exp(-t * 35) * 0.6
    return verb(stereo(norm(k + snap, 0.9), 0), 0.45, 0.2)


def stamp():
    t = t_(0.9)
    thock = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) + np.sin(2 * np.pi * 95 * t) * np.exp(-t * 14) * 0.8
    paper = band_sweep(rng.standard_normal(len(t)), 2500, 900, 0.7) * np.exp(-t * 22) * 0.6
    a = verb(stereo(norm(thock + paper, 0.9), 0), 0.5, 0.22) * 0.9
    b = impact(False) * 0.35
    out = np.zeros((max(len(a), len(b)), 2))
    out[: len(a)] += a
    out[: len(b)] += b
    return out


def riser(dur=1.8):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    x = band_sweep(rng.standard_normal(n), 300, 9000, 0.45)
    tone = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (t * 2)) / SR) * 0.25
    return verb(stereo(norm((x + tone) * t ** 2.5, 0.85), 0), 0.5, 0.2)


def shimmer(dur=1.2, grains=22, seed=5):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    outL, outR = np.zeros(n), np.zeros(n)
    for _ in range(grains):
        st = int(r.uniform(0, dur * 0.7) * SR)
        f = r.uniform(2400, 7200)
        g = bell(f, 0.35, 14, r.uniform(0.25, 0.6))
        p = r.uniform(-0.8, 0.8)
        m = min(len(g), n - st)
        outL[st : st + m] += g[:m] * np.cos((p + 1) * np.pi / 4)
        outR[st : st + m] += g[:m] * np.sin((p + 1) * np.pi / 4)
    return verb(norm(np.stack([outL, outR], 1), 0.7), 0.7, 0.35)


def confetti():
    r = np.random.default_rng(9)
    n = int(0.9 * SR)
    out = np.zeros((n, 2))
    for i in range(16):
        st = int(r.uniform(0, 0.55) * SR)
        p = pop(r.uniform(1100, 2600)) * r.uniform(0.15, 0.4)
        m = min(len(p), n - st)
        out[st : st + m] += p[:m]
    return norm(out, 0.7)


def success():
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate((1174.66, 1479.98, 1760.0, 2349.32)):
        b = bell(f, 1.0, 4.5, 0.8)
        o = int(i * 0.075 * SR)
        out[o : o + len(b)] += b[: len(out) - o]
    return verb(stereo(norm(out, 0.8), 0), 0.5, 0.25)


def chime():
    out = np.zeros(int(2.6 * SR))
    for f, a in ((1174.66, 1.0), (1760.0, 0.6), (2349.32, 0.4)):
        out += bell(f, 2.6, 1.6, a)
    return verb(stereo(norm(out, 0.6), 0), 0.8, 0.35)


def count_roll(dur=0.9, ticks=22):
    out = np.zeros((int((dur + 0.1) * SR), 2))
    tk = tick()
    for i in range(ticks):
        u = i / (ticks - 1)
        t0 = dur * (1 - (1 - u) ** 1.8) * 0.98
        o = int(t0 * SR)
        out[o : o + len(tk)] += tk[: len(out) - o] * (0.6 + 0.4 * u)
    return out


def shutter():
    out = np.zeros((int(0.35 * SR), 2))
    for o, g in ((0, 1.0), (0.055, 0.8)):
        t = t_(0.05)
        x = band_sweep(rng.standard_normal(len(t)), 3000, 1200, 0.6) * np.exp(-t * 90)
        x += np.sin(2 * np.pi * 140 * t) * np.exp(-t * 70) * 0.6
        s = stereo(norm(x, 0.8) * g, 0)
        i = int(o * SR)
        out[i : i + len(s)] += s
    return verb(out, 0.2, 0.1)


def flip():
    n = int(0.38 * SR)
    t = np.linspace(0, 1, n)
    x = band_sweep(rng.standard_normal(n), 900, 3500, 0.5) * np.sin(np.pi * t) ** 1.2
    x *= 0.7 + 0.3 * np.sin(2 * np.pi * 26 * t)
    return verb(pan_sweep(norm(x, 0.8), -0.5, 0.5), 0.3, 0.15)


def spark():
    n = int(0.6 * SR)
    t = np.linspace(0, 0.6, n)
    crackle = np.zeros(n)
    r = np.random.default_rng(3)
    for _ in range(26):
        i = int(r.uniform(0, 0.35) * SR)
        crackle[i : i + 60] += r.standard_normal(60) * np.linspace(1, 0, 60) * r.uniform(0.3, 1)
    whoomp = band_sweep(rng.standard_normal(n), 200, 1200, 0.6) * np.sin(np.pi * np.clip(t / 0.5, 0, 1)) ** 2
    return verb(stereo(norm(crackle * 0.5 + whoomp, 0.8), 0), 0.4, 0.2)


LIB = {
    "whoosh": whoosh, "whoosh_up": whoosh_up, "whoosh_fast": whoosh_fast, "whoosh_long": whoosh_long,
    "swish": swish, "suck": suck, "pop": pop, "pop2": pop2, "pop3": pop3, "click": click, "tick": tick,
    "ding": ding, "ding2": ding2, "msg_in": msg_in, "msg_out": msg_out, "impact": impact,
    "impact_soft": impact_soft, "hit": hit, "stamp": stamp, "riser": riser, "shimmer": shimmer,
    "confetti": confetti, "success": success, "chime": chime, "count_roll": count_roll,
    "shutter": shutter, "flip": flip, "spark": spark,
}


def load(name, cache={}):
    if name in cache:
        return cache[name]
    override = SAMPLES / f"{name}.wav"
    if name.endswith("_rev"):
        x = load(name[:-4])[::-1].copy()
    elif override.exists():
        x, sr = sf.read(override, always_2d=True)
        if sr != SR:
            from scipy.signal import resample_poly
            x = resample_poly(x, SR, sr, axis=0)
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        x = norm(x, 0.9)
    else:
        x = LIB[name]()
    cache[name] = x
    return x


def render(cues, duration):
    out = np.zeros((int(duration * SR) + SR, 2))
    for t, name, gain in cues:
        s = load(name)
        i = int(round(t * SR))
        if i < 0:
            s, i = s[-i:], 0
        m = min(len(s), len(out) - i)
        out[i : i + m] += s[:m] * gain
    out = out[: int(duration * SR)]
    board = Pedalboard([HighpassFilter(35), Compressor(threshold_db=-14, ratio=3, attack_ms=2, release_ms=90),
                        Limiter(threshold_db=-3)])
    y = board(out.T.astype(np.float32), SR).T
    return y


if __name__ == "__main__":
    W = timeline.words()
    E = timeline.events(W)
    C = timeline.cues(E, W, style=STYLE)
    y = render(C, timeline.DURATION)
    # the effects step back while the voice speaks (build.py also carves the voice's bands out of them)
    # only a slight dip under the voice: the effects are short, and they should be heard
    y = y * (1 - (1 - 10 ** (-4 / 20)) * timeline.voice_activity(len(y), SR, attack=0.03, release=0.15))[:, None]
    (ROOT / "assets" / "audio").mkdir(parents=True, exist_ok=True)
    sf.write(ROOT / "assets" / "audio" / f"{'sfx_apple' if STYLE else 'sfx'}{timeline.SUFFIX}.wav", y * 0.8, SR)
    print("sfx cues:", len(C), "peak", float(np.max(np.abs(y))))
