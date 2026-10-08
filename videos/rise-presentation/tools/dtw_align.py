"""Word timings of a voice-over line, by aligning it to a reference reading whose timings are known.

No speech recogniser is needed: the local Kokoro voice reads the same line through a copy of
its model that also reports each phoneme's duration, so the reference's word boundaries are
exact; dynamic time warping on MFCCs then maps them onto the real take. Accurate to a few
hundredths of a second where the old loudness-and-syllables estimate could be off by a word.
"""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

CACHE = Path.home() / ".cache" / "hyperframes" / "tts"
MODEL = CACHE / "models" / "kokoro-v1.0.onnx"
TIMED = CACHE / "models" / "kokoro-v1.0-timed.onnx"
SR = 16000
HOP = 160  # 10 ms
SAY = {"RISE": "Raïze"}  # Kokoro spells capitals out
PUNCT = re.compile(r"[,:;.…!?»]+")


def timed_model():
    """A copy of the Kokoro model that also outputs each phoneme's duration (built once)."""
    if not TIMED.exists():
        import onnx
        from onnx import TensorProto, helper
        m = onnx.load(str(MODEL))
        m.graph.node.append(helper.make_node("Identity", ["/encoder/Gather_output_0"], ["duration"], name="duration_out"))
        m.graph.output.append(helper.make_tensor_value_info("duration", TensorProto.INT64, None))
        onnx.save(m, str(TIMED))
    return TIMED


@lru_cache(maxsize=1)
def kokoro():
    import kokoro_onnx
    return kokoro_onnx.Kokoro(str(timed_model()), str(CACHE / "voices" / "voices-v1.0.bin"))


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
    """Kokoro reading of the line: audio at SR and each word's (start, end) in it."""
    import librosa
    k = kokoro()
    tokens = [say(t) for t in text.split()]
    audio, sr, timing = k.create_timed(" ".join(tokens), voice=voice, lang="fr-fr", speed=speed)
    # phoneme groups between spaces, in order
    groups, cur = [], []
    for t in timing:
        if t.phoneme == " ":
            if cur:
                groups.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        groups.append(cur)
    # how many groups each text token produces when read on its own
    counts = [max(1, len(k.tokenizer.phonemize(tok, "fr-fr").split())) if not PUNCT.fullmatch(tok) else 1
              for tok in tokens]
    if sum(counts) != len(groups):
        raise ValueError(f"cannot map {len(groups)} phoneme groups onto {len(tokens)} words: {text!r}")
    spans, i = [], 0
    for tok, n in zip(tokens, counts):
        g = [t for grp in groups[i : i + n] for t in grp if not PUNCT.fullmatch(t.phoneme)]
        spans.append((tok, (g[0].start, g[-1].end) if g else None))
        i += n
    # join standalone punctuation to the word before
    words = []
    for tok, span in spans:
        if words and PUNCT.fullmatch(tok):
            continue
        words.append(span)
    return librosa.resample(np.asarray(audio, dtype=np.float32), orig_sr=sr, target_sr=SR), words


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


def align(path, text):
    """Word timings in the line's audio: ([{"w", "start", "end"}], speech start, speech end)."""
    import librosa
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    ref, spans = reference(text)
    ref_sq, rs, ro = squeeze(ref)
    y_sq, ys, yo = squeeze(y)
    _, wp = librosa.sequence.dtw(X=features(ref_sq), Y=features(y_sq), metric="euclidean")
    wp = wp[::-1]

    def to_real(t):
        i = min(int(round(np.interp(t, ro, rs) * SR / HOP)), wp[-1, 0])
        return float(np.interp(np.median(wp[wp[:, 0] == i, 1]) * HOP / SR, ys, yo))
    shown = words_of(text)
    starts, ends = [], []
    for span in spans:
        a, b = (to_real(span[0]), to_real(span[1])) if span else (ends[-1], ends[-1])
        starts.append(max(a, starts[-1] + 0.05) if starts else a)  # every word gets its own beat
        ends.append(max(b, starts[-1] + 0.04))
    out = [{"w": w, "start": round(a, 3), "end": round(b, 3)} for w, a, b in zip(shown, starts, ends)]
    return out, out[0]["start"], out[-1]["end"]
