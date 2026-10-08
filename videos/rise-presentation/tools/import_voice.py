"""Import a full voice-over take (one file, the lines read in order) into assets/vo/.

The take is split at the pauses between lines: among all the silences, the cuts
whose share of the spoken time best matches each line's share of the syllables
win. Inside a line, pauses longer than MAX_PAUSE are shortened, a slow read is
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


def split(x, n_lines, weights):
    voiced = voicing(x)
    sil, t0, t1 = silences(voiced)
    K = n_lines - 1
    if len(sil) < K:
        raise SystemExit(f"only {len(sil)} pauses found, need {K}: is this the full take?")
    target = np.cumsum(weights)[:-1] / sum(weights)  # each cut's share of the syllables
    spoken = np.cumsum(voiced)
    cands = [((a + b) / 2, b - a) for a, b in sil]
    pos = [spoken[min(len(spoken) - 1, int(c / HOP))] / spoken[-1] for c, _ in cands]  # share of the spoken time
    # dynamic programming: K increasing cuts, close to their target, preferring real pauses
    INF = 1e9
    M = len(cands)
    score = lambda j, k: abs(pos[j] - target[k]) * 30 - min(cands[j][1], 0.6)
    cost = [[INF] * M for _ in range(K)]
    back = [[-1] * M for _ in range(K)]
    for j in range(M):
        cost[0][j] = score(j, 0)
    for k in range(1, K):
        for j in range(M):
            c = score(j, k)
            for i in range(j):
                if cost[k - 1][i] + c < cost[k][j]:
                    cost[k][j] = cost[k - 1][i] + c
                    back[k][j] = i
    j = int(np.argmin(cost[K - 1]))
    picks = [j]
    for k in range(K - 1, 0, -1):
        j = back[k][j]
        picks.append(j)
    cuts = [cands[p][0] for p in sorted(picks)]
    bounds = [t0] + cuts + [t1]
    return [(bounds[i], bounds[i + 1]) for i in range(n_lines)]


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
    parts = split(x, len(keys), weights)
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
