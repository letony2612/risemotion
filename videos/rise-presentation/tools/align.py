"""Rough word timings for a voice-over line, from the audio alone.

No speech model is needed: the line's speech is found from its loudness, the
pauses are snapped to the punctuation, and the words between two pauses share
the voiced time in proportion to their syllables. Precise enough (~0.1 s) to
time burned-in captions and kinetic words.
"""
import re

import numpy as np
import soundfile as sf

VOWELS = "aeiouyàâäéèêëîïôöùûüœæ"


def syllables(word):
    w = re.sub(r"[^a-zàâäéèêëîïôöùûüœæç]", "", word.lower())
    if not w:
        return 1
    groups = re.findall(f"[{VOWELS}]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("ée", "ie")):
        n -= 1  # silent final e
    return max(1, n)


def align(path, text, hop=0.01):
    audio, sr = sf.read(path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    win = int(0.03 * sr)
    step = int(hop * sr)
    frames = max(1, (len(audio) - win) // step)
    rms = np.array([np.sqrt(np.mean(audio[i * step : i * step + win] ** 2) + 1e-12) for i in range(frames)])
    db = 20 * np.log10(rms)
    voiced = db > db.max() - 32
    # close tiny gaps (stops inside words)
    idx = np.where(voiced)[0]
    first, last = idx[0], idx[-1]
    pauses = []
    i = first
    while i <= last:
        if not voiced[i]:
            j = i
            while j <= last and not voiced[j]:
                j += 1
            if (j - i) * hop >= 0.04:
                pauses.append(((i) * hop, (j) * hop))
            i = j
        else:
            i += 1
    t0, t1 = first * hop, (last + 1) * hop

    words = []
    for tok in text.split():
        if words and re.fullmatch(r"[,:;.…!?»]+", tok):
            words[-1] += "\u00a0" + tok  # French spacing before : ; ! ?
        else:
            words.append(tok)
    weights = [syllables(w) for w in words]
    total = sum(weights)
    # expected time of each word boundary if speech were uniform
    cum = np.cumsum(weights)
    punct = [k for k, w in enumerate(words[:-1]) if re.search(r"[,:;.…!?]$", w)]
    speech = t1 - t0 - sum(b - a for a, b in pauses)
    snapped = {}
    used = set()
    last_pi = -1
    for k in punct:
        expect = t0 + speech * cum[k] / total
        best, bestscore = None, 0.6
        for pi, (a, b) in enumerate(pauses):
            if pi <= last_pi:
                continue  # keep pauses in order
            score = abs(a - expect) - 0.8 * (b - a)
            if score < bestscore:
                best, bestscore = pi, score
        if best is not None:
            last_pi = best
            snapped[k] = pauses[best]
    # build segments separated by snapped pauses
    bounds = sorted(snapped.items())
    segs = []
    start_word, seg_t = 0, t0
    for k, (a, b) in bounds:
        segs.append((start_word, k, seg_t, a))
        start_word, seg_t = k + 1, b
    segs.append((start_word, len(words) - 1, seg_t, t1))
    out = []
    for w0, w1, a, b in segs:
        ws = weights[w0 : w1 + 1]
        tot = sum(ws)
        t = a
        for k, wt in zip(range(w0, w1 + 1), ws):
            d = (b - a) * wt / tot
            out.append({"w": words[k], "start": round(t, 3), "end": round(t + d, 3)})
            t += d
    return out, round(t0, 3), round(t1, 3)


if __name__ == "__main__":
    import json, sys
    res, a, b = align(sys.argv[1], sys.argv[2])
    print(json.dumps({"speech": [a, b], "words": res}, ensure_ascii=False, indent=1))
