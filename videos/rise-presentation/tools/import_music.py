"""Import a music track (e.g. the Lyria piece from FLORA) as the video's music bed.

Analyses tempo, beats and energy, prints the loudest/quietest bars so the edit
can be matched to the track, and writes assets/audio/music_source.wav fitted to
the video length: trimmed with a fade, or extended by repeating whole bars from
the middle of the track when it is too short.
Usage: python3 tools/import_music.py path/to/music.mp3 [--report]
"""
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402

ROOT = T.ROOT
SR = 44100


def analyse(path):
    y, sr = librosa.load(path, sr=SR, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    mono = y.mean(axis=0)
    tempo, beats = librosa.beat.beat_track(y=mono, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=512)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    return y, mono, tempo, beats, rms, times


def report(path):
    y, mono, tempo, beats, rms, times = analyse(path)
    dur = y.shape[1] / SR
    print(f"duration {dur:.2f}s  tempo {tempo:.1f} BPM  beats {len(beats)}  first beat {beats[0]:.2f}s")
    bar = 4 * 60 / tempo
    print("energy per 2 s (dB):")
    for t0 in np.arange(0, dur, 2.0):
        m = (times >= t0) & (times < t0 + 2)
        if m.any():
            db = 20 * np.log10(rms[m].mean() + 1e-9)
            print(f"  {t0:5.1f}-{t0 + 2:5.1f}s  {db:6.1f}  " + "#" * max(0, int(db + 40)))
    return y, tempo, beats, bar


def fit(path, target=T.DURATION):
    y, tempo, beats, bar = report(path)
    n_target = int(target * SR)
    if y.shape[1] >= n_target:
        out = y[:, :n_target]
    else:
        # repeat whole bars from the middle of the track until it is long enough
        b0 = beats[0]
        mid = b0 + bar * max(1, int((y.shape[1] / SR - b0) / bar / 2) - 1)
        loop = y[:, int(mid * SR) : int((mid + 2 * bar) * SR)]
        head, tail = y[:, : int(mid * SR)], y[:, int(mid * SR) :]
        parts = [head]
        while sum(p.shape[1] for p in parts) + tail.shape[1] < n_target:
            parts.append(loop)
        out = np.concatenate(parts + [tail], axis=1)[:, :n_target]
        print(f"extended: repeated {len(parts) - 1} x 2 bars from {mid:.2f}s")
    fade = np.interp(np.arange(out.shape[1]) / SR, [0, target - 1.5, target], [1, 1, 0])
    out = out * fade
    out = out / (np.max(np.abs(out)) or 1) * 0.89
    dest = ROOT / "assets" / "audio" / "music_source.wav"
    sf.write(dest, out.T, SR)
    print("written", dest.relative_to(ROOT))


if __name__ == "__main__":
    if "--report" in sys.argv:
        report(sys.argv[1])
    else:
        fit(sys.argv[1])
