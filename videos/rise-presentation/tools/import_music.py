"""Use a music track (e.g. the Lyria piece from FLORA) as the video's music bed.

Import:  python3 tools/import_music.py path/to/music.mp3
  -> assets/audio/music_track.wav (the track, untouched) and a report of its tempo and drop.
Every build (compose_music.py) then fits it to the edit: whole bars are taken out of
(or repeated in) the groove before the drop so that the drop lands on the quiz, the
track starts inside its first bar to absorb the remainder, and it fades out with the film.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SR = 44100
TRACK = ROOT / "assets" / "audio" / "music_track.wav"
XFADE = 0.03


def analyse(y):
    import librosa
    mono = y.mean(axis=0)
    dur = y.shape[1] / SR
    tempo, tracked = librosa.beat.beat_track(y=mono, sr=SR, units="time")
    # a steady grid over the whole track (the tracker skips quiet passages): the tracked
    # tempo, snapped to a whole BPM when it is that close, and the phase that sits on the onsets
    p0 = 60 / float(np.atleast_1d(tempo)[0])
    period = np.polyfit(np.round((tracked - tracked[0]) / p0), tracked, 1)[0]
    if abs(60 / period - round(60 / period)) < 0.6:
        period = 60 / round(60 / period)
    onset = librosa.onset.onset_strength(y=mono, sr=SR, hop_length=512)
    ot = librosa.times_like(onset, sr=SR, hop_length=512)
    grid = lambda ph: ph + period * np.arange(int((dur - ph) / period) + 1)
    phase = max(np.arange(0, period, 0.004), key=lambda ph: np.interp(grid(ph), ot, onset).sum())
    beats = grid(phase)
    tempo, bar = 60 / period, 4 * period
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=512)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=512)
    energy = lambda a, b: float(rms[(times >= a) & (times < b)].mean())
    # the drop: the beat after which two bars are loudest compared with the bar before
    ref = np.percentile(rms, 95)
    best, drop = 0.0, None
    for i, b in enumerate(beats):
        if b < 0.3 * dur or b + 2 * bar > dur:
            continue
        jump = (energy(b, b + 2 * bar) - energy(b - bar, b)) / ref
        if jump > best:
            best, drop = jump, i
    if best < 0.25:  # no clear drop: the track is used as it comes
        drop = None
    return tempo, beats, bar, drop, best


def splice(a, b):
    n = min(int(XFADE * SR), a.shape[1], b.shape[1])
    w = np.sqrt(np.linspace(0, 1, n))
    return np.concatenate([a[:, :-n], a[:, -n:] * w[::-1] + b[:, :n] * w, b[:, n:]], axis=1)


def fit(y, drop_at, duration):
    """Return the track cut so that its drop lands at drop_at (s), duration long, faded out."""
    tempo, beats, bar, d, score = analyse(y)
    s = lambda t: int(round(t * SR))
    if d is None:
        out, note = y, "no clear drop, used from the start"
    else:
        drop = beats[d]
        p = max(4, d - 8)  # keep the two bars of build-up before the drop
        shift = drop - drop_at
        if shift >= 0:  # too late: take whole bars out of the groove before the build-up
            k = 0
            while p - 4 * (k + 1) >= 4 and beats[p] - beats[p - 4 * (k + 1)] <= shift:
                k += 1
            c = p - 4 * k
            s0 = shift - (beats[p] - beats[c])
            if k and s0 < beats[c] - bar:
                out = splice(y[:, s(s0) : s(beats[c])], y[:, s(beats[p]) :])
            else:  # no groove to spare: start the track later instead
                k, s0, out = 0, shift, y[:, s(shift) :]
            note = f"drop {drop:.2f}s -> {drop_at:.2f}s: {k} bar(s) out of the groove, start {s0:.2f}s in"
        else:  # too early: repeat whole bars of the groove before the build-up
            k = int(np.ceil(-shift / bar))
            c = max(0, p - 4 * k)
            extra = beats[p] - beats[c]
            s0 = max(0.0, drop + extra - drop_at)
            head = splice(y[:, s(s0) : s(beats[p])], y[:, s(beats[c]) : s(beats[p])])
            out = splice(head, y[:, s(beats[p]) :])
            note = f"drop {drop:.2f}s -> {drop_at:.2f}s: {k} bar(s) repeated, start {s0:.2f}s in"
    n = s(duration)
    out = out[:, :n]
    if out.shape[1] < n:
        out = np.pad(out, ((0, 0), (0, n - out.shape[1])))
    t = np.arange(n) / SR
    out = out * np.interp(t, [0, 0.02, duration - 1.5, duration], [0, 1, 1, 0])
    print(f"music: {tempo:.1f} BPM, {note}")
    return out


def load(path):
    y, sr = sf.read(path, always_2d=True)
    assert sr == SR, sr
    return y.T


def main(path):
    TRACK.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "2", "-ar", str(SR), str(TRACK)], check=True)
    y = load(TRACK)
    tempo, beats, bar, d, score = analyse(y)
    print(f"{TRACK.relative_to(ROOT)}: {y.shape[1] / SR:.1f}s, {tempo:.1f} BPM, first beat {beats[0]:.2f}s")
    print(f"drop at {beats[d]:.2f}s (strength {score:.2f})" if d is not None else "no clear drop found")
    print("rebuild (python3 tools/build.py) to fit it to the edit")


if __name__ == "__main__":
    main(sys.argv[1])
