"""Use a music track (e.g. the Lyria piece from FLORA) as the video's music bed.

Import:  python3 tools/import_music.py path/to/music.mp3
  -> assets/audio/music_track.<ext> (the file as given) and music_track.json (its tempo,
     beat grid, drop and end).
Every build then fits it to the edit (compose_music.py): whole bars of the groove ahead of
the build-up are taken out (or repeated) so that the drop lands on the quiz, and around the
end card the track jumps, on a bar line, to the bars that close it, so the music ends on its
own last hit. timeline.py lengthens the film by less than a bar to let that ending land.
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SR = 44100
AUDIO = ROOT / "assets" / "audio"
INFO = AUDIO / "music_track.json"
XFADE = 0.03
BUILD_BARS = 4  # bars of build-up kept ahead of the drop
TAIL = 0.4  # film left after the music's last sound
CLEAR = 2.0  # a bar's kick counts when its best phase scores that much above the median


def analyse(y):
    import librosa
    mono = y.mean(axis=0)
    dur = y.shape[1] / SR
    tempo = float(np.atleast_1d(librosa.feature.tempo(y=mono, sr=SR))[0])
    # a steady grid over the whole track, set on the kick drum: the tempo near the rough
    # estimate (whose error can reach a BPM, a beat lost every minute) and the phase that put
    # the most low, percussive onsets on the grid; a whole BPM wins when it is that close
    hop = 128
    S = np.abs(librosa.stft(mono, n_fft=2048, hop_length=hop))
    perc = librosa.decompose.hpss(S)[1]
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    norm = lambda e: e / (e.max() + 1e-9)
    kick = norm(np.maximum(0, np.diff(np.log1p(perc[freqs < 160].sum(axis=0)), prepend=0)))
    env = kick + 0.5 * norm(librosa.onset.onset_strength(S=librosa.amplitude_to_db(perc), sr=SR, hop_length=hop))
    et = librosa.times_like(env, sr=SR, hop_length=hop)

    def fit_grid(bpms):
        best = (-1.0, None, None)
        for bpm in bpms:
            period = 60 / bpm
            phases = np.arange(0, period, 0.002)
            pts = phases[:, None] + period * np.arange(int(dur / period))[None, :]
            score = np.interp(pts, et, env, right=0).sum(axis=1)
            if score.max() > best[0]:
                best = (float(score.max()), period, float(phases[score.argmax()]))
        return best[1], best[2]

    period, phase = fit_grid(np.arange(tempo - 2, tempo + 2, 0.02))
    if abs(60 / period - round(60 / period)) < 0.1:
        period, phase = fit_grid([round(60 / period)])
    grid = lambda ph: ph + period * np.arange(int((dur - ph) / period) + 1)
    beats = grid(phase)
    bar = 4 * period
    # each bar's own kick phase (a generated track drifts by a few ms): its offset from the grid, and how clear it is
    cand = np.arange(-0.06, 0.0601, 0.002)
    bars = []
    for t0 in phase + bar * np.arange(int((dur - phase) / bar)):
        sc = np.interp(t0 + cand[:, None] + period * np.arange(4)[None, :], et, kick, right=0).sum(axis=1)
        bars.append([round(float(cand[sc.argmax()]), 3), round(float(sc.max() / (np.median(sc) + 1e-9)), 2)])
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=512)[0]
    times = librosa.times_like(rms, sr=SR, hop_length=512)
    ref = np.percentile(rms, 95)
    energy = lambda a, b: float(rms[(times >= a) & (times < b)].mean())
    # the drop: the first beat after which two bars jump above the bar before (nearly) as much as anywhere
    jumps = {i: (energy(b, b + 2 * bar) - energy(b - bar, b)) / ref
             for i, b in enumerate(beats) if b >= 2 * bar and b + 2 * bar <= dur}
    best = max(jumps.values())
    drop = next(i for i in sorted(jumps) if jumps[i] >= 0.85 * best) if best >= 0.25 else None
    stop = float(times[np.where(rms > 0.05 * ref)[0][-1]])  # the track's last sound
    return {"tempo": round(60 / period, 2), "period": float(period), "phase": float(phase), "drop": drop,
            "strength": round(float(best), 2), "stop": round(stop, 3), "length": round(dur, 3), "bars": bars}


def beat(info, k):
    return info["phase"] + k * info["period"]


def kick(info, t):
    """The kick's offset from the grid in the bar around t (0 where that bar has no clear kick)."""
    bars = info.get("bars", [])
    k = int((t - info["phase"]) // (4 * info["period"]))
    return bars[k][0] if 0 <= k < len(bars) and bars[k][1] >= CLEAR else 0.0


def ending(info, drop_at, duration_min):
    """Film length that lets the track's own end land TAIL before the film's (less than a bar added)."""
    if info["drop"] is None:
        return duration_min
    bar = 4 * info["period"]
    a = drop_at + info["stop"] - beat(info, info["drop"])  # where the track would stop, uncut after the drop
    m = math.floor((a - (duration_min - TAIL)) / bar)
    if m < 1:
        return duration_min
    return math.ceil((a - m * bar + TAIL) * 10) / 10


def plan(info, drop_at, cut_at, duration):
    """The pieces of the track (start, end) laid end to end, and a note on the cuts."""
    if info["drop"] is None:
        return [(0.0, None)], "no clear drop: used from the start"
    P, d = info["period"], info["drop"]
    bar, td = 4 * P, beat(info, d)
    off = kick(info, td)  # everything from the build-up on is set so the drop's own kick lands on drop_at
    p = max(4, d - 4 * BUILD_BARS)  # the build-up ahead of the drop stays whole
    shift = td - drop_at
    if shift >= 0:  # drop too late: whole bars out of the groove ahead of the build-up
        k = 0
        while p - 4 * (k + 1) >= 4 and 4 * (k + 1) * P <= shift:
            k += 1
        s0 = shift - 4 * k * P
        if k and s0 < beat(info, p - 4 * k) - bar:
            segs = [(s0, beat(info, p - 4 * k)), (beat(info, p) + off, None)]
        else:
            k, s0, segs = 0, shift, [(shift + off, None)]
        note = f"drop {td:.2f}s -> {drop_at:.2f}s: {k} bar(s) out, start {s0:.2f}s in"
    else:  # drop too early: whole bars of the groove repeated
        k = math.ceil(-shift / bar)
        c = max(0, p - 4 * k)
        s0 = max(0.0, td + (p - c) * P - drop_at)
        segs = [(s0, beat(info, p)), (beat(info, c) + off, beat(info, p) + off), (beat(info, p) + off, None)]
        note = f"drop {td:.2f}s -> {drop_at:.2f}s: {k} bar(s) repeated, start {s0:.2f}s in"
    # the ending: whole bars skipped near the end card so the track's last hit closes the film
    a = drop_at + info["stop"] - td
    m = math.ceil((a - (duration - TAIL)) / bar - 1e-6)
    if m >= 1:
        i = max(2, round((cut_at - drop_at) / bar))
        ta, tb = td + i * bar, td + (i + m) * bar
        if tb < info["stop"] - bar:  # leave on the grid, land on the destination's own kick
            segs[-1] = (segs[-1][0], ta + off)
            segs.append((tb + kick(info, tb), None))
            note += f"; at {drop_at + i * bar:.2f}s, {m} bar(s) ahead to the track's ending ({a - m * bar:.2f}s)"
    return segs, note


def splice(a, b):
    n = min(int(XFADE * SR), a.shape[1], b.shape[1])
    w = np.sqrt(np.linspace(0, 1, n))
    return np.concatenate([a[:, :-n], a[:, -n:] * w[::-1] + b[:, :n] * w, b[:, n:]], axis=1)


def fit(y, info, drop_at, cut_at, duration):
    """The track cut to the edit: its drop on drop_at, its ending on the end card, duration long."""
    segs, note = plan(info, drop_at, cut_at, duration)
    s = lambda t: int(round(t * SR))
    pre = int(XFADE * SR)  # each later piece starts a crossfade early, so the joins keep the timing
    out = None
    for a, b in segs:
        piece = y[:, max(0, s(a) - (pre if out is not None else 0)) : (s(b) if b is not None else None)]
        out = piece if out is None else splice(out, piece)
    n = s(duration)
    out = out[:, :n]
    if out.shape[1] < n:
        out = np.pad(out, ((0, 0), (0, n - out.shape[1])))
    natural_end = "ending" in note
    t = np.arange(n) / SR
    out = out * np.interp(t, [0, 0.02, duration - (0.25 if natural_end else 1.5), duration], [0, 1, 1, 0])
    print(f"music: {info['tempo']} BPM, {note}")
    return out


def track():
    """The imported track (the file as given), or None."""
    return next((p for p in sorted(AUDIO.glob("music_track.*")) if p.suffix != ".json"), None)


def load(path):
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "track.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "2", "-ar", str(SR), str(wav)], check=True)
        y, _ = sf.read(wav, always_2d=True)
    return y.T


def main(path):
    AUDIO.mkdir(parents=True, exist_ok=True)
    for old in AUDIO.glob("music_track.*"):
        old.unlink()
    dest = AUDIO / ("music_track" + Path(path).suffix.lower())
    shutil.copyfile(path, dest)
    info = analyse(load(dest))
    INFO.write_text(json.dumps(info, indent=1))
    print(f"{dest.relative_to(ROOT)}: {info['length']:.1f}s, {info['tempo']} BPM, ends at {info['stop']:.2f}s")
    print(f"drop at {beat(info, info['drop']):.2f}s (strength {info['strength']})" if info["drop"] is not None
          else "no clear drop found")
    print("rebuild (python3 tools/build.py) to fit it to the edit")


if __name__ == "__main__":
    main(sys.argv[1])
