"""Single source of truth for the RISE video timing.

The voice-over drives the edit, as in a social ad: the lines run on one after
the other with only the take's own short breath (capped so the read never
stalls), nothing waits for the picture, and every move is keyed to a word.
Word times come from dtw_align.py (cached in assets/vo/words.json), so captions
and kinetic beats land on the words. build.py injects these times into index.html, sfx.py renders the
sound design from cues() and compose_music.py follows the same sections, so
picture, sound effects and music cannot drift apart.

To swap the voice: python3 tools/import_voice.py take.mp3 && python3 tools/build.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
BPM = 120  # tempo of the synthesized bed (compose_music.py)
MAX_GAP = 0.3  # longest breath kept between two lines
MAX_DURATION = 30.0  # the brief: 15 to 30 s
MUSIC = ROOT / "assets" / "audio" / "music_track.json"  # an imported track (tools/import_music.py)

# Voice-over lines: (text as spoken, text shown in the captions). Same number of words in both.
LINES = {
    "l1": ("Ta foi, tu la vis que le dimanche ?", "Ta foi, tu la vis que le dimanche ?"),
    "l2": ("Avec RISE, tu la vis tous les jours.", "Avec RISE, tu la vis tous les jours."),
    "l3": ("Tu partages ce que Dieu fait dans ta vie.", "Tu partages ce que Dieu fait dans ta vie."),
    "l4": ("Un coup dur ? Tes frères et sœurs prient pour toi.", "Un coup dur ? Tes frères et sœurs prient pour toi."),
    "l5": ("Et quand Dieu répond… tout le monde célèbre !", "Et quand Dieu répond… tout le monde célèbre !"),
    "l6": ("Trouve ton groupe : louange, étude biblique, jeunes.",
           "Trouve ton groupe : louange, étude biblique, jeunes."),
    "l7": ("Chaque matin, ta Parole du jour.", "Chaque matin, ta Parole du jour."),
    "l8": ("Un kwiz par jour pour apprendre la Bible !", "Un quiz par jour pour apprendre la Bible !"),
    "l9": ("Télécharge RISE, c'est cent pour cent gratuit !", "Télécharge RISE, c'est cent pour cent gratuit !"),
}

# Captions in two tiers, as in a social ad: a small setup label, then the punch line, which lands on
# its first word. (line, setup word range or None, punch word ranges swapped in place one by one)
BEATS = [
    ("l1", (0, 4), [(5, 7)]),
    ("l2", (0, 4), [(5, 7)]),
    ("l3", (0, 1), [(2, 8)]),
    ("l4", None, [(0, 2)]),
    ("l4", (3, 6), [(7, 9)]),
    ("l5", (0, 3), [(4, 7)]),
    ("l6", (0, 2), [(3, 3), (4, 5), (6, 6)]),
    ("l7", (0, 1), [(2, 5)]),
    ("l8", (0, 3), [(4, 7)]),
    ("l9", (0, 1), [(2, 6)]),
]
PUNCH_TEXT = {("l9", 2): "c'est 100 % gratuit !"}  # shown instead of the words (same timing)


def _tokens(text):
    out = []
    for tok in text.split():
        if out and tok in (":", ";", "!", "?", "»"):
            out[-1] += " " + tok
        else:
            out.append(tok)
    return out


def _natural_gaps():
    take = ROOT / "assets" / "vo" / "take.json"
    keys = list(LINES)
    gaps = {k: 0.25 for k in keys}
    if take.exists():
        t = json.loads(take.read_text())
        if all(k in t for k in keys):
            for a, b in zip(keys, keys[1:]):
                gaps[a] = min(MAX_GAP, max(0.08, t[b]["start"] - t[a]["end"]))
    return gaps


def _align(k, spoken, f, cache):
    """Word timings of a line: warped from a reference reading (dtw_align), cached per text and audio;
    the loudness-and-syllables estimate (align.py) only if that fails."""
    import hashlib
    sha = hashlib.sha1(f.read_bytes()).hexdigest()
    hit = cache.get(k)
    if hit and hit["text"] == spoken and hit["audio"] == sha:
        return hit["words"]
    try:
        from dtw_align import align
        words = align(f, spoken)[0]
    except Exception as e:  # noqa: BLE001 - any failure falls back to the rough estimate
        print(f"{k}: reference alignment failed ({e}), rough estimate used")
        from align import align
        return align(str(f), spoken)[0]
    cache[k] = {"text": spoken, "audio": sha, "words": words}
    return words


def _plan():
    dur, rel = {}, {}
    cache_file = ROOT / "assets" / "vo" / "words.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    for k, (spoken, shown) in LINES.items():
        f = ROOT / "assets" / "vo" / f"{k}.wav"
        dur[k] = sf.info(str(f)).duration
        words = _align(k, spoken, f, cache)
        shown_words = _tokens(shown)
        assert len(words) == len(shown_words), (k, len(words), len(shown_words))
        rel[k] = [(sw, w["start"], w["end"]) for sw, w in zip(shown_words, words)]
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    gap = _natural_gaps()
    music = json.loads(MUSIC.read_text()) if MUSIC.exists() else None
    V, E = {}, {}
    wt = lambda k, i: V[k] + rel[k][i][1]
    end = lambda k: V[k] + dur[k]
    keys = list(LINES)
    # the read never waits for the picture: each line follows the previous one after its breath
    V["l1"] = 0.3
    for a, b in zip(keys, keys[1:]):
        V[b] = end(a) + gap[a]

    # 1. hook: a week where only Sunday counts
    E["hook"] = 0.0
    E["week_in"] = 0.05
    E["w_dim"] = wt("l1", 7)  # dimanche
    # 2. "Avec RISE": the phone rises, then every day of the week lights up
    E["logo_land"] = wt("l2", 1)  # RISE
    E["splash2"] = E["logo_land"] - 0.85  # the logo animation: its letters burst out 0.85 s in
    E["days"] = wt("l2", 5)  # tous les jours
    E["days_end"] = max(end("l2"), E["days"] + 0.6)
    E["week_out"] = E["days_end"] + 0.1
    E["phone_in"] = E["days_end"] - 0.1
    # 3. share: a testimony lifts out of the feed
    E["share"] = V["l3"] - 0.12
    E["lift_post"] = wt("l3", 1)  # partages
    E["w_dieu"] = wt("l3", 4)
    E["w_vie"] = wt("l3", 8)
    # 4. pray: a hard time, the community prays
    E["pray"] = V["l4"] - 0.12
    E["lift_prayer"] = wt("l4", 1)  # coup dur
    E["jeprie"] = wt("l4", 7)  # prient
    E["upd1"] = E["jeprie"] + 0.2
    E["upd2"] = E["jeprie"] + 0.4
    # 5. answered: "répond" stamps it, everybody celebrates
    E["answer"] = V["l5"] - 0.12
    E["stamp"] = wt("l5", 3) + 0.08  # répond
    E["celebrate"] = wt("l5", 4)  # tout le monde
    E["w_celebre"] = wt("l5", 7)
    # 6. groups: rows lift as they are named
    E["groups"] = V["l6"] - 0.12
    E["hl1"], E["hl2"], E["hl3"] = wt("l6", 3), wt("l6", 4), wt("l6", 6)
    # 7. verse of the day
    E["verse"] = V["l7"] - 0.12
    E["verse_lift"] = wt("l7", 2)  # ta Parole
    # 8. quiz (the music drops on it)
    E["quiz"] = V["l8"] - 0.05
    E["q_tap"] = wt("l8", 2)  # par
    E["q_ok"] = wt("l8", 3) + 0.1  # jour
    E["learn"] = wt("l8", 5)  # apprendre la Bible
    # 9. end card
    E["end"] = V["l9"] - 0.12
    E["w_rise9"] = wt("l9", 1)
    E["splash9"] = E["w_rise9"] - 0.85  # the logo's letters burst out on "RISE"
    E["free"] = wt("l9", 2)  # c'est 100 % gratuit
    E["stores"] = max(end("l9") + 0.05, E["free"] + 0.5)
    duration = math.ceil((E["stores"] + 2.0) * 10) / 10
    if music:  # a little longer, so the track ends on its own last hit
        from import_music import ending
        landed = ending(music, E["quiz"], duration)
        duration = landed if landed <= MAX_DURATION else duration

    W = {k: [{"w": sw, "t": round(float(V[k] + a), 3), "e": round(float(V[k] + b), 3)} for sw, a, b in rel[k]] for k in LINES}
    E = {k: round(float(v), 3) for k, v in E.items()}
    V = {k: round(float(v), 3) for k, v in V.items()}
    return E, V, W, duration, dur


E, VO_START, W, DURATION, VO_DUR = _plan()
S = {k: E[k] for k in ("hook", "share", "pray", "answer", "groups", "verse", "quiz", "end")}


def words():
    return W


def voice_activity(n, sr, attack=0.08, release=0.3):
    """0..1 over n samples at sr: 1 while the voice-over speaks, with a soft attack and release."""
    t = np.arange(n) / sr
    on = np.zeros(n)
    for k, start in VO_START.items():
        on[(t >= start - attack) & (t < start + VO_DUR[k] + release)] = 1.0
    w = max(1, int(attack * sr))
    return np.convolve(on, np.ones(w) / w, mode="same")


def events(_W=None):
    return E


def cues(E=E, W=W):
    """Sound design cue sheet: (time, sound, gain)."""
    c = []
    # captions: a light tick when a setup label lands, a pop under each punch line
    for line, setup, punches in BEATS:
        if setup:
            c.append((W[line][setup[0]]["t"] - 0.03, "tick", 0.3))
        for a, _ in punches:
            c.append((W[line][a]["t"] - 0.03, "swish", 0.35))
    # 1. hook: the week pops in, only Sunday lights up
    for i in range(7):
        c.append((E["week_in"] + i * 0.05, "pop" if i % 2 == 0 else "pop2", 0.3))
    c += [(E["w_dim"], "ding", 0.55), (E["w_dim"] + 0.02, "shimmer", 0.35)]
    # 2. RISE: the phone rises, the whole week lights up
    c += [(E["phone_in"], "whoosh_up", 0.75), (E["logo_land"], "impact_soft", 0.6), (E["logo_land"] + 0.02, "chime", 0.4)]
    for i in range(7):
        c.append((E["days"] + i * 0.07, "pop3" if i % 2 else "pop", 0.35 + i * 0.04))
    c += [(E["days"] + 0.5, "confetti", 0.45), (E["week_out"], "whoosh_fast", 0.6)]
    # 3. share
    c += [(E["share"], "swish", 0.45), (E["lift_post"] - 0.05, "whoosh", 0.5), (E["lift_post"], "pop", 0.5),
          (E["w_dieu"], "pop2", 0.45), (E["w_vie"], "pop3", 0.5)]
    # 4. pray
    c += [(E["pray"], "whoosh_fast", 0.7), (E["lift_prayer"], "hit", 0.55), (E["jeprie"], "click", 0.85),
          (E["jeprie"] + 0.1, "count_roll", 0.45), (E["upd1"], "ding", 0.45), (E["upd2"], "ding2", 0.45)]
    # 5. answered
    c += [(E["answer"], "flip", 0.7), (E["stamp"], "stamp", 1.0), (E["stamp"] + 0.04, "shimmer", 0.55),
          (E["celebrate"], "confetti", 0.6), (E["celebrate"] + 0.1, "pop", 0.5), (E["celebrate"] + 0.35, "pop2", 0.5),
          (E["celebrate"] + 0.6, "pop3", 0.5)]
    # 6. groups
    c += [(E["groups"], "whoosh", 0.6), (E["hl1"], "pop", 0.6), (E["hl2"], "pop2", 0.6), (E["hl3"], "pop3", 0.6)]
    # 7. verse
    c += [(E["verse"], "whoosh_long", 0.55), (E["verse"] + 0.2, "shimmer", 0.4), (E["verse_lift"], "chime", 0.4)]
    # 8. quiz (drop)
    c += [(E["quiz"], "impact", 0.9), (E["q_tap"], "click", 0.85), (E["q_ok"], "success", 0.65),
          (E["learn"], "whoosh_up", 0.55), (E["learn"] + 0.05, "count_roll", 0.5), (E["learn"] + 0.5, "pop", 0.55),
          (E["learn"] + 0.65, "pop2", 0.55), (E["learn"] + 0.8, "pop3", 0.6), (E["learn"] + 0.6, "confetti", 0.5)]
    # 9. end
    c += [(E["end"], "whoosh", 0.55), (E["w_rise9"], "impact", 0.9), (E["w_rise9"] + 0.02, "chime", 0.5),
          (E["free"], "success", 0.55), (E["free"] + 0.05, "confetti", 0.5), (E["stores"], "pop", 0.4), (E["stores"] + 0.12, "pop2", 0.4),
          (DURATION - 1.4, "shimmer", 0.3)]
    return sorted(c)


if __name__ == "__main__":
    print(f"duration {DURATION}s")
    for k in LINES:
        print(f"{k}: {VO_START[k]:6.2f} -> {VO_START[k] + VO_DUR[k]:6.2f}   {LINES[k][1][:50]}")
    print({k: E[k] for k in S})
