"""Import a full voice-over take (one file, the lines read in order) into assets/vo/.

The take is split at the pauses between lines: a reference reading of the script
is warped onto the take (dtw_align.py) and each break between two lines lands in
one of its pauses (a share-of-syllables guess put "jeunes" in the wrong line,
because one pause inside a line can be longer than the one between two). Inside a line, pauses longer than MAX_PAUSE are shortened, a slow read is
brought up to an ad pace (at most TEMPO_MAX faster, pitch kept), and the voice
gets a light broadcast polish so it sits on top of the music.
Usage: python3 tools/import_voice.py path/to/voice.mp3
Then: python3 tools/build.py  (and check the scene windows it prints)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402
from align import syllables  # noqa: E402

ROOT = T.ROOT
SR = 44100
HOP = 0.01
MAX_PAUSE = 0.4  # longest pause kept inside a line (s)
TARGET_RATE = 5.2  # syllables per second of an ad read
TEMPO_MAX = 1.12


def load(path):
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
        x, _ = sf.read(wav)
    return x


def voicing(x, floor=38):
    win = int(0.03 * SR)
    st = int(HOP * SR)
    n = max(1, (len(x) - win) // st)
    db = np.array([20 * np.log10(np.sqrt(np.mean(x[i * st : i * st + win] ** 2)) + 1e-9) for i in range(n)])
    return db > db.max() - floor


def silences(voiced, min_len=0.07):
    idx = np.where(voiced)[0]
    first, last = idx[0], idx[-1]
    out, i = [], first
    while i <= last:
        if not voiced[i]:
            j = i
            while j <= last and not voiced[j]:
                j += 1
            if (j - i) * HOP >= min_len:
                out.append((i * HOP, j * HOP))
            i = j
        else:
            i += 1
    return out, first * HOP, (last + 1) * HOP


def split(x, keys):
    """Cut the take into its lines. A reference reading of the script is warped onto the take
    (dtw_align) to say roughly where each line ends; among the pauses near there, the cuts kept
    are those whose lines best match their own reference readings."""
    import librosa
    from functools import lru_cache
    from dtw_align import SR as DSR, fit_cost, line_breaks
    sil, t0, t1 = silences(voicing(x))
    texts = [T.LINES[k][0] for k in keys]
    y16 = librosa.resample(x, orig_sr=SR, target_sr=DSR)
    targets = line_breaks(y16, texts)
    mids = [(a + b) / 2 for a, b in sil]
    near = lambda tg: sorted(range(len(mids)), key=lambda j: abs(mids[j] - tg))
    # candidate pauses per break: within 1.5 s of where the warp puts it (always at least the nearest)
    cands = [sorted({j for j in near(tg)[:1]} | {j for j, m in enumerate(mids) if abs(m - tg) <= 1.5}) for tg in targets]
    edge = lambda j: mids[j] if j >= 0 else (t0 if j == -1 else t1)

    @lru_cache(maxsize=None)
    def cost(i, a, b):  # line i spoken between pause a and pause b (-1: take start, -2: take end)
        s0, s1 = edge(a), edge(b)
        if s1 - s0 < 0.3:
            return 1e9
        return fit_cost(y16[int(s0 * DSR) : int(s1 * DSR)], texts[i])

    # dynamic programming over the breaks: total cost of the lines, a little pull towards the warp's guess
    best = {j: (cost(0, -1, j) + 0.02 * abs(mids[j] - targets[0]), [j]) for j in cands[0]}
    for i in range(1, len(targets)):
        nxt = {}
        for j in cands[i]:
            opts = [(c + cost(i, a, j) + 0.02 * abs(mids[j] - targets[i]), path + [j])
                    for a, (c, path) in best.items() if mids[a] < mids[j]]
            if opts:
                nxt[j] = min(opts)
        best = nxt
    total, path = min((c + cost(len(keys) - 1, path[-1], -2), path) for c, path in best.values())
    for tg, j in zip(targets, path):
        a, b = sil[j]
        print(f"break near {tg:6.2f}s -> pause {a:.2f}-{b:.2f}s")
    bounds = [t0] + [mids[j] for j in path] + [t1]
    return [(bounds[i], bounds[i + 1]) for i in range(len(keys))]


def trim(seg, pad=0.04):
    win = int(0.02 * SR)
    st = int(0.005 * SR)
    n = max(1, (len(seg) - win) // st)
    db = np.array([20 * np.log10(np.sqrt(np.mean(seg[i * st : i * st + win] ** 2)) + 1e-9) for i in range(n)])
    v = np.where(db > db.max() - 40)[0]
    a = max(0, v[0] * st - int(pad * SR))
    b = min(len(seg), v[-1] * st + win + int(pad * SR))
    return seg[a:b].copy(), a / SR


def tighten(seg):
    """Shorten the pauses inside a line to MAX_PAUSE (short crossfade at each join)."""
    sil, _, _ = silences(voicing(seg, floor=40), min_len=MAX_PAUSE + 0.05)
    if not sil:
        return seg
    f = int(0.012 * SR)
    out, pos = [], 0
    for a, b in sil:
        keep = MAX_PAUSE / 2
        cut0, cut1 = int((a + keep) * SR), int((b - keep) * SR)
        out.append(seg[pos:cut0])
        pos = cut1
    out.append(seg[pos:])
    y = out[0]
    for part in out[1:]:
        fade = np.linspace(0, 1, min(f, len(y), len(part)))
        n = len(fade)
        y = np.concatenate([y[:-n], y[-n:] * (1 - fade) + part[:n] * fade, part[n:]])
    return y


def fade_edges(seg):
    f = int(0.01 * SR)
    seg[:f] *= np.linspace(0, 1, f)
    seg[-f:] *= np.linspace(1, 0, f)
    return seg


def polish(segs):
    """Broadcast polish: low rumble out, gentle compression, a little presence; one gain for every line."""
    from pedalboard import Compressor, HighpassFilter, PeakFilter, Pedalboard
    chain = Pedalboard([HighpassFilter(80), Compressor(threshold_db=-22, ratio=3, attack_ms=4, release_ms=90),
                        PeakFilter(3200, 2.5, 0.8)])
    out = {k: chain(s.astype(np.float32)[None, :], SR)[0].astype(np.float64) for k, s in segs.items()}
    peak = max(np.max(np.abs(s)) for s in out.values()) or 1
    return {k: s / peak * 0.89 for k, s in out.items()}


def main(path):
    x = load(path)
    keys = list(T.LINES)
    weights = [sum(syllables(w) for w in T.LINES[k][0].split()) for k in keys]
    parts = split(x, keys)
    segs, natural = {}, {}
    for k, (a, b) in zip(keys, parts):
        seg, lead = trim(x[int(a * SR) : int(b * SR)])
        natural[k] = (a + lead, a + lead + len(seg) / SR)
        segs[k] = tighten(seg)
    rate = sum(weights) / sum(len(s) / SR for s in segs.values())
    tempo = float(np.clip(TARGET_RATE / rate, 1.0, TEMPO_MAX))
    print(f"read at {rate:.1f} syll/s -> tempo x{tempo:.2f}")
    if tempo > 1.001:
        from pedalboard import time_stretch
        segs = {k: time_stretch(s.astype(np.float32)[None, :], SR, stretch_factor=tempo)[0] for k, s in segs.items()}
    segs = polish(segs)
    (ROOT / "assets" / "vo").mkdir(parents=True, exist_ok=True)
    take, t = {}, 0.0
    for i, k in enumerate(keys):
        seg = fade_edges(np.asarray(segs[k], dtype=np.float64))
        sf.write(ROOT / "assets" / "vo" / f"{k}.wav", seg, SR)
        if i:
            t += (natural[k][0] - natural[keys[i - 1]][1]) / tempo  # the take's own breath, at the new pace
        take[k] = {"start": round(t, 3), "end": round(t + len(seg) / SR, 3)}
        t += len(seg) / SR
        r = weights[i] / (len(seg) / SR)
        print(f"{k}: {len(seg) / SR:5.2f}s  {r:4.1f} syll/s  {T.LINES[k][1][:56]}")
    (ROOT / "assets" / "vo" / "take.json").write_text(json.dumps(take, indent=1))
    print("line positions written to assets/vo/take.json (rebuild to re-time the edit)")


if __name__ == "__main__":
    main(sys.argv[1])
