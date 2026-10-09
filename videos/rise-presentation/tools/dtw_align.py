"""Word timings of a voice-over line, by aligning it to a reference reading whose timings are known.

No speech recogniser is needed: the local Kokoro voice reads the line twice, fluently and one word
at a time (so the word boundaries of the second reading are exact); a first warp carries those
boundaries onto the fluent reading, and dynamic time warping on MFCCs and loudness (pauses squeezed
out of both sides) then maps them onto the real take. Words that follow a pause are finally set on
the pause's end, where the voice audibly resumes.
"""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

CACHE = Path.home() / ".cache" / "hyperframes" / "tts"
MODEL = CACHE / "models" / "kokoro-v1.0.onnx"
SR = 16000
HOP = 160  # 10 ms
SAY = {"RISE": "Raïze"}  # Kokoro spells capitals out
PUNCT = re.compile(r"[,:;.…!?»]+")


@lru_cache(maxsize=1)
def kokoro():
    import kokoro_onnx
    return kokoro_onnx.Kokoro(str(MODEL), str(CACHE / "voices" / "voices-v1.0.bin"))


def say(token):
    core = token.strip(".,!?:;")
    return token.replace(core, SAY[core]) if core in SAY else token


def words_of(text):
    """The line's words, standalone punctuation joined to the word before (as align.py does)."""
    out = []
    for tok in text.split():
        if out and PUNCT.fullmatch(tok):
            out[-1] += " " + tok
        else:
            out.append(tok)
    return out


def reference(text, voice="ff_siwis", speed=1.0):
    """Kokoro reading of the line: audio at SR and each word's (start, end) in it.

    Kokoro's own phoneme durations drift from its audio by up to 0.2 s, so the word boundaries come
    from a second reading, one word at a time (where every boundary is exact by construction),
    warped onto the fluent reading: same voice, same phonemes, so that warp is tight."""
    import librosa
    k = kokoro()
    to16 = lambda a, sr: librosa.resample(np.asarray(a, dtype=np.float32), orig_sr=sr, target_sr=SR)
    said = " ".join(say(t) for t in text.split())
    fluent = to16(*k.create(said, voice=voice, lang="fr-fr", speed=speed))
    pieces, bounds, t = [], [], 0.0
    gap = np.zeros(int(0.03 * SR), dtype=np.float32)
    for w in words_of(said):  # punctuation stays on its word, for its intonation
        a = to16(*k.create(w, voice=voice, lang="fr-fr", speed=speed))
        pieces += [a, gap]
        bounds.append((t, t + len(a) / SR))
        t += (len(a) + len(gap)) / SR
    to_fluent = warp(np.concatenate(pieces), fluent)
    spans = [(to_fluent(a), to_fluent(b)) for a, b in bounds]
    starts = snap([a for a, _ in spans], onsets(fluent))
    return fluent, [(a, max(b, a + 0.04)) for a, (_, b) in zip(starts, spans)]


def onsets(y, floor=35, min_pause=0.06):
    """Times where speech resumes after a pause of at least min_pause seconds."""
    import librosa
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=HOP)[0]
    loud = 20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - floor
    k = int(min_pause * SR / HOP)
    return [i * HOP / SR for i in range(len(loud)) if loud[i] and (i == 0 or (i >= k and not loud[i - k : i].any()))]


def snap(starts, ons, reach=0.25):
    """Move each word start onto a nearby speech onset, keeping the words in order."""
    out = list(starts)
    for i, t in enumerate(out):
        lo = out[i - 1] + 0.08 if i else -1.0
        hi = starts[i + 1] - 0.05 if i + 1 < len(starts) else t + reach
        near = [o for o in ons if abs(o - t) <= reach and lo < o < hi]
        if near:
            out[i] = min(near, key=lambda o: abs(o - t))
    return out


ENERGY_WEIGHT = 3.0


def features(y):
    """Normalised MFCCs plus a heavily weighted loudness row, so pauses line up with pauses."""
    import librosa
    m = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=21, n_fft=400, hop_length=HOP)[1:]
    m = (m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-6)
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=HOP)[0]
    db = 20 * np.log10(rms + 1e-5)
    e = np.clip((db - db.max() + 40) / 40, 0, 1)  # 0 = silence, 1 = loudest
    return np.vstack([m, ENERGY_WEIGHT * np.sqrt(m.shape[0]) * (e - 0.5)[None, :]])


def squeeze(y, keep=0.04, floor=35):
    """Every pause cut down to `keep` seconds, so that pauses of different lengths cannot pull the
    warping off course; returns the squeezed signal and breakpoints (squeezed time, original time)."""
    import librosa
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=HOP)[0]
    loud = 20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - floor
    pieces, bp, t_sq, k, n = [], [(0.0, 0.0)], 0.0, 0, len(loud)
    while k < n:
        j = k
        while j < n and loud[j] == loud[k]:
            j += 1
        a, b = k * HOP, min(len(y), j * HOP)
        if not loud[k] and (b - a) / SR > keep:  # a pause: keep its middle `keep` seconds
            mid, half = (a + b) // 2, int(keep * SR / 2)
            pieces.append(y[mid - half : mid + half])
            bp += [(t_sq, a / SR), (t_sq + keep, b / SR)]
            t_sq += keep
        else:
            pieces.append(y[a:b])
            t_sq += (b - a) / SR
            bp.append((t_sq, b / SR))
        k = j
    bp = np.array(bp)
    return np.concatenate(pieces), bp[:, 0], bp[:, 1]


def warp(ref, y):
    """Map a time in the reference reading to the matching time in the take (both mono at SR)."""
    import librosa
    ref_sq, rs, ro = squeeze(ref)
    y_sq, ys, yo = squeeze(y)
    _, wp = librosa.sequence.dtw(X=features(ref_sq), Y=features(y_sq), metric="euclidean")
    wp = wp[::-1]

    def to_real(t):
        i = min(int(round(np.interp(t, ro, rs) * SR / HOP)), wp[-1, 0])
        return float(np.interp(np.median(wp[wp[:, 0] == i, 1]) * HOP / SR, ys, yo))
    return to_real


def fit_cost(y, text):
    """How well a stretch of take matches a reading of `text`: mean warping cost per step (lower is better)."""
    import librosa
    ref, _ = reference(text)
    X, Y = features(squeeze(ref)[0]), features(squeeze(y)[0])
    D, wp = librosa.sequence.dtw(X=X, Y=Y, metric="euclidean")
    return float(D[-1, -1] / len(wp))


def align(path, text):
    """Word timings in the line's audio: ([{"w", "start", "end"}], speech start, speech end)."""
    import librosa
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    ref, spans = reference(text)
    to_real = warp(ref, y)
    shown = words_of(text)
    warped = snap([to_real(span[0]) for span in spans], onsets(y))
    starts, ends = [], []
    for a, span in zip(warped, spans):
        b = to_real(span[1])
        starts.append(max(a, starts[-1] + 0.05) if starts else a)  # every word gets its own beat
        ends.append(max(b, starts[-1] + 0.04))
    out = [{"w": w, "start": round(a, 3), "end": round(b, 3)} for w, a, b in zip(shown, starts, ends)]
    return out, out[0]["start"], out[-1]["end"]


def line_breaks(y, lines, gap=0.3):
    """Where each line ends in a full take (mono at SR): the take is warped onto a reference reading
    of all the lines, and each break between two reference lines lands in the take."""
    pieces, breaks, t = [], [], 0.0
    for i, text in enumerate(lines):
        ref, _ = reference(text)
        pieces.append(ref)
        t += len(ref) / SR
        if i < len(lines) - 1:
            pieces.append(np.zeros(int(gap * SR), dtype=ref.dtype))
            breaks.append(t + gap / 2)
            t += gap
    to_real = warp(np.concatenate(pieces), y)
    return [to_real(b) for b in breaks]
