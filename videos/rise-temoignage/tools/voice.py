"""Tony's voice (his ElevenLabs take, the whole of SCRIPT.md read in one go) made into the film's soundtrack.

The take is cut into its lines, the script sentence by sentence as the film shows them (LINES): a reference
reading of the script is warped onto the take (dtw_align, from rise-presentation) to say roughly where each line
ends, and the cut falls in the take's pause nearest there. Inside a line, pauses are cut down to MAX_PAUSE; between
two lines the pause is the one LINES gives, short to keep the pace, held longer where a beat makes the next line
land (before « C'est justement pour ça que j'ai créé RISE »). The words are never touched, nor their speed. Then a
light broadcast polish, and each word's time for the captions and the drawings (dtw_align again, line by line).
Usage: python3 tools/voice.py path/to/take.mp3  -> assets/voice/voice.wav, assets/voice/take.json
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "rise-presentation" / "tools"))
OUT = ROOT / "assets" / "voice"
SR = 44100
HOP = 0.01
MAX_PAUSE = 0.38  # longest pause kept inside a line (s)
FLOOR = 30  # dB under the take's loudest where its voice stops
LUFS = -15.0  # loud enough for a phone, under what TikTok turns down

LINES = [  # each line as he says it, and the pause before it (s)
    ("Toi aussi, t'as peur de déranger ?", 0.0),
    ("Moi, tout le temps.", 0.45),
    ("Et pourtant… j'ai créé un réseau social.", 0.55),
    ("Moi c'est Tony.", 0.6),
    ("Pendant longtemps, j'ai été quelqu'un de renfermé.", 0.45),
    ("Le genre de personne qui n'osait pas poser de questions.", 0.35),
    ("Peut-être par peur de dire n'importe quoi…", 0.35),
    ("…ou par peur de déranger.", 0.3),
    ("J'ai souvent été rabaissé.", 0.6),
    ("Par des amis, par des proches, même par des profs…", 0.35),
    ("À force d'entendre ce genre de paroles, j'ai fini par me créer des barrières.", 0.5),
    ("J'avais peur du jugement, du regard des autres.", 0.35),
    ("Aller vers les gens était devenu difficile.", 0.35),
    ("Et aujourd'hui encore, ça me freine dans ma foi.", 0.5),
    ("Pourtant, je pense qu'on a tous besoin de frères et sœurs autour de nous pour apprendre, partager et avancer avec Dieu.", 0.5),
    ("C'est justement pour ça que j'ai créé RISE.", 0.8),
    ("Pour offrir une communauté à ceux qui, comme moi, n'osent pas toujours aller vers les autres.", 0.6),
    ("Un endroit où partager leurs témoignages, poser leurs questions, demander de la prière et rejoindre des groupes.", 0.35),
    ("Parce que je voulais créer l'espace dont j'ai moi-même besoin pour grandir dans ma foi.", 0.7),
]


def load(path):
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
        x, _ = sf.read(wav)
    return x


def level(x):
    """Loudness (dB) every HOP, over 30 ms."""
    win, st = int(0.03 * SR), int(HOP * SR)
    n = max(1, (len(x) - win) // st)
    return np.array([20 * np.log10(np.sqrt(np.mean(x[i * st:i * st + win] ** 2)) + 1e-9) for i in range(n)])


def voicing(x, top, floor=FLOOR):
    """Where it is voiced, every HOP: louder than floor dB under top, the take's loudest (its pauses hold breath
    and hiss some 35 dB down, which must not count as voice)."""
    return level(x) > top - floor


def silences(voiced, min_len=0.07):
    """The pauses (start, end) between the first and the last voiced moment, and those two moments."""
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


def split(x, texts, pull=0.2):
    """The take cut into its lines (as rise-presentation's import_voice.py does): the warped reference says
    roughly where each line ends; among the pauses near there, the cuts kept are those whose lines best match
    their own reference readings (a pause inside a line, after a comma, can be as long as one between two)."""
    import librosa
    from functools import lru_cache
    from dtw_align import SR as DSR, fit_cost, line_breaks
    sil, t0, t1 = silences(voicing(x, level(x).max()), min_len=0.04)
    y16 = librosa.resample(x, orig_sr=SR, target_sr=DSR)
    targets = line_breaks(y16, texts)
    mids = [(a + b) / 2 for a, b in sil]
    near = lambda tg: sorted(range(len(mids)), key=lambda j: abs(mids[j] - tg))
    cands = [sorted({near(tg)[0]} | {j for j, m in enumerate(mids) if abs(m - tg) <= 0.8}) for tg in targets]
    edge = lambda j: mids[j] if j >= 0 else (t0 if j == -1 else t1)

    @lru_cache(maxsize=None)
    def cost(i, a, b):  # line i said between pause a and pause b (-1: the take's start, -2: its end)
        s0, s1 = edge(a), edge(b)
        if s1 - s0 < 0.3:
            return 1e9
        return fit_cost(y16[int(s0 * DSR):int(s1 * DSR)], texts[i])

    best = {j: (cost(0, -1, j) + pull * abs(mids[j] - targets[0]), [j]) for j in cands[0]}
    for i in range(1, len(targets)):
        nxt = {}
        for j in cands[i]:
            opts = [(c + cost(i, a, j) + pull * abs(mids[j] - targets[i]), path + [j]) for a, (c, path) in best.items() if mids[a] < mids[j]]
            if opts:
                nxt[j] = min(opts)
        best = nxt
    _, path = min((c + cost(len(texts) - 1, path[-1], -2), path) for c, path in best.values())
    for tg, j in zip(targets, path):
        print(f"break near {tg:6.2f}s -> pause {sil[j][0]:.2f}-{sil[j][1]:.2f}s")
    bounds = [t0] + [mids[j] for j in path] + [t1]
    return [(bounds[i], bounds[i + 1]) for i in range(len(texts))]


def trim(seg, top, pad=0.06):
    """The line without the silence round it (a little kept, so no soft ending is clipped)."""
    v = np.where(voicing(seg, top))[0]
    return seg[max(0, int((v[0] * HOP - pad) * SR)):min(len(seg), int(((v[-1] + 3) * HOP + pad) * SR))].copy()


def tighten(seg, top):
    """The pauses inside a line cut down to MAX_PAUSE (a short crossfade at each join)."""
    sil, _, _ = silences(voicing(seg, top), min_len=MAX_PAUSE + 0.05)
    if not sil:
        return seg
    parts, pos = [], 0
    for a, b in sil:
        parts.append(seg[pos:int((a + MAX_PAUSE / 2) * SR)])
        pos = int((b - MAX_PAUSE / 2) * SR)
    parts.append(seg[pos:])
    y, f = parts[0], int(0.012 * SR)
    for part in parts[1:]:
        fade = np.linspace(0, 1, min(f, len(y), len(part)))
        n = len(fade)
        y = np.concatenate([y[:-n], y[-n:] * (1 - fade) + part[:n] * fade, part[n:]])
    return y


def loudness(y):
    """Integrated loudness (LUFS), as ffmpeg's EBU R128 meter reads it."""
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "y.wav"
        sf.write(wav, y, SR)
        log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(log.rsplit("I:", 1)[1].split("LUFS")[0])


def polish(y):
    """Low rumble out, gentle compression, a little presence, brought to LUFS with a safety limiter."""
    from pedalboard import Compressor, HighpassFilter, Limiter, PeakFilter, Pedalboard
    y = Pedalboard([HighpassFilter(80), Compressor(threshold_db=-24, ratio=2.5, attack_ms=5, release_ms=100),
                    PeakFilter(3200, 2.0, 0.8)])(y.astype(np.float32)[None, :], SR)[0].astype(np.float64)
    y *= 10 ** ((LUFS - loudness(y)) / 20)
    return Pedalboard([Limiter(threshold_db=-1.5, release_ms=60)])(y.astype(np.float32)[None, :], SR)[0].astype(np.float64)


def main(path):
    from dtw_align import align
    x = load(path)
    texts = [t for t, _ in LINES]
    top = level(x).max()
    segs = [tighten(trim(x[int(a * SR):int(b * SR)], top), top) for a, b in split(x, texts)]
    for s in segs:
        f = int(0.01 * SR)
        s[:f] *= np.linspace(0, 1, f)
        s[-f:] *= np.linspace(1, 0, f)
    pieces, spans, t = [], [], 0.0
    for (text, gap), seg in zip(LINES, segs):
        pieces += [np.zeros(int(gap * SR)), seg]
        t += gap
        spans.append((t, t + len(seg) / SR))
        t += len(seg) / SR
    pieces.append(np.zeros(int(0.3 * SR)))
    voice = polish(np.concatenate(pieces))
    OUT.mkdir(parents=True, exist_ok=True)
    sf.write(OUT / "voice.wav", voice, SR, subtype="PCM_16")
    lines = []
    with tempfile.TemporaryDirectory() as d:
        for i, ((text, _), (a, b)) in enumerate(zip(LINES, spans)):
            wav = Path(d) / f"{i}.wav"
            sf.write(wav, voice[int(a * SR):int(b * SR)], SR)
            words, _, _ = align(wav, text)
            lines.append({"text": text, "start": round(a, 3), "end": round(b, 3),
                          "words": [{"w": w["w"], "start": round(a + w["start"], 3), "end": round(a + w["end"], 3)} for w in words]})
            print(f"{a:6.2f}-{b:6.2f}  {text}")
    (OUT / "take.json").write_text(json.dumps({"duration": round(len(voice) / SR, 3), "lines": lines}, ensure_ascii=False, indent=1))
    print(f"{len(x) / SR:.1f}s read -> {len(voice) / SR:.1f}s", OUT / "voice.wav")


if __name__ == "__main__":
    main(sys.argv[1])
