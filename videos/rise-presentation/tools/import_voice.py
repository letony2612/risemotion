"""Import a full voice-over take (one file, the 9 lines read in order) into assets/vo/.

The take is split at the pauses between lines: among all the silences, the 8
cuts that best match the expected length of each line (by syllables) win.
Usage: python3 tools/import_voice.py path/to/voice.mp3
Then: python3 tools/build.py  (and check the scene windows it prints)
"""
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


def load(path):
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
        x, _ = sf.read(wav)
    return x


def silences(x, hop=0.01, min_len=0.18):
    win = int(0.03 * SR)
    st = int(hop * SR)
    n = (len(x) - win) // st
    db = np.array([20 * np.log10(np.sqrt(np.mean(x[i * st : i * st + win] ** 2)) + 1e-9) for i in range(n)])
    voiced = db > db.max() - 38
    idx = np.where(voiced)[0]
    first, last = idx[0], idx[-1]
    out, i = [], first
    while i <= last:
        if not voiced[i]:
            j = i
            while j <= last and not voiced[j]:
                j += 1
            if (j - i) * hop >= min_len:
                out.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    return out, first * hop, (last + 1) * hop


def split(x, n_lines, weights):
    sil, t0, t1 = silences(x)
    total = sum(weights)
    target = np.cumsum(weights)[:-1] / total  # expected cut positions (fraction of speech)
    cands = [((a + b) / 2, b - a) for a, b in sil]
    K = n_lines - 1
    if len(cands) < K:
        raise SystemExit(f"only {len(cands)} pauses found, need {K}: is this the full take?")
    pos = [(c - t0) / (t1 - t0) for c, _ in cands]
    # dynamic programming: choose K increasing candidates minimising position error, rewarding long pauses
    INF = 1e9
    M = len(cands)
    cost = [[INF] * M for _ in range(K)]
    back = [[-1] * M for _ in range(K)]
    for j in range(M):
        cost[0][j] = abs(pos[j] - target[0]) * 10 - cands[j][1]
    for k in range(1, K):
        for j in range(M):
            c = abs(pos[j] - target[k]) * 10 - cands[j][1]
            for i in range(j):
                if cost[k - 1][i] + c < cost[k][j]:
                    cost[k][j] = cost[k - 1][i] + c
                    back[k][j] = i
    j = int(np.argmin(cost[K - 1]))
    picks = [j]
    for k in range(K - 1, 0, -1):
        j = back[k][j]
        picks.append(j)
    picks = sorted(picks)
    cuts = [cands[p][0] for p in picks]
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
    out = seg[a:b].copy()
    f = int(0.01 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out


def main(path):
    x = load(path)
    keys = list(T.VO)
    weights = [sum(syllables(w) for w in T.VO[k][1].split()) for k in keys]
    parts = split(x, len(keys), weights)
    (ROOT / "assets" / "vo" / "raw").mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(x)) or 1
    for k, (a, b) in zip(keys, parts):
        seg = trim(x[int(a * SR) : int(b * SR)]) / peak * 0.89
        sf.write(ROOT / "assets" / "vo" / f"{k}.wav", seg, SR)
        start = T.VO[k][0]
        print(f"{k}: {len(seg) / SR:5.2f}s  (starts {start:5.2f} -> ends {start + len(seg) / SR:5.2f})  {T.VO[k][2][:48]}")


if __name__ == "__main__":
    main(sys.argv[1])
