"""Single source of truth for the RISE video timing.

The voice-over drives the edit: each scene starts when its line starts, lines
follow each other with a short breath (the take's own, capped so the read never
stalls), the next line may begin a beat before its picture (the voice leads the
cut, as in an ad), and a scene only waits when its picture needs a beat more.
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
BPM = 120
BEAT = 60 / BPM
MAX_GAP = 0.3  # longest breath kept between two lines
MAX_DURATION = 30.0  # the brief: 15 to 30 s
MUSIC = ROOT / "assets" / "audio" / "music_track.json"  # an imported track (tools/import_music.py)

# Voice-over lines: (text as spoken, text shown in the captions). Same number of words in both.
LINES = {
    "l1": ("La foi, ça se vit ensemble !", "La foi, ça se vit ensemble !"),
    "l2": ("Sur RISE, partage ce que Dieu fait dans ta vie !", "Sur RISE, partage ce que Dieu fait dans ta vie !"),
    "l3": ("Un coup dur ? Tes frères et sœurs prient pour toi.", "Un coup dur ? Tes frères et sœurs prient pour toi."),
    "l4": ("Et quand Dieu répond, on célèbre ensemble !", "Et quand Dieu répond, on célèbre ensemble !"),
    "l5": ("Trouve ton groupe : louange, étude biblique, jeunes !",
           "Trouve ton groupe : louange, étude biblique, jeunes !"),
    "l6": ("Chaque matin, ta Parole du jour.", "Chaque matin, ta Parole du jour."),
    "l7": ("Et chaque jour, un niveau de kwiz : toute la Bible en un an !",
           "Et chaque jour, un niveau de quiz : toute la Bible en un an !"),
    "l8": ("RISE. Élève-toi. Ensemble ! Dispo sur iPhone et Android.",
           "RISE. Élève-toi. Ensemble ! Dispo sur iPhone et Android."),
}

# Caption chunks: word index ranges (inclusive) per line; l1 and l8 are carried by the big type.
# Each chunk ends where the voice pauses, so its last word stays up; the widest pill is 737 px,
# clear of the platform buttons on the right.
CHUNKS = {
    "l2": [(0, 2), (3, 9)],
    "l3": [(0, 2), (3, 6), (7, 9)],
    "l4": [(0, 3), (4, 6)],
    "l5": [(0, 2), (3, 3), (4, 5), (6, 6)],
    "l6": [(0, 1), (2, 5)],
    "l7": [(0, 2), (3, 6), (7, 12)],
}
# Words shown in amber inside the captions (compared without punctuation, lower case).
KEYWORDS = {"dieu", "vie", "prient", "répond", "célèbre", "louange", "biblique", "jeunes", "parole", "quiz", "bible"}


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


def _ceil_beat(t):
    return math.ceil(t / BEAT - 1e-6) * BEAT


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
    grid = music["period"] if music else BEAT
    V, E = {}, {}
    wt = lambda k, i: V[k] + rel[k][i][1]
    end = lambda k: V[k] + dur[k]
    after = lambda k, t: max(t, end(k) + gap[k])  # next line: once the previous one has breathed

    # 1. hook: the flame, the words, the logo; "Sur RISE" is said on the logo
    V["l1"] = 0.35
    E["hook"] = 0.0
    E["spark"] = 0.05
    E["w_foi"], E["w_vit"], E["w_ensemble"] = wt("l1", 0), wt("l1", 2), wt("l1", 5)
    E["collapse"] = max(E["w_ensemble"] + 0.7, 2.1)
    E["letters"] = E["collapse"] + 0.3
    E["logo_land"] = E["letters"] + 0.55
    V["l2"] = after("l1", E["logo_land"] + 0.12)
    E["hook_out"] = max(E["logo_land"] + 0.6, wt("l2", 1) + 0.3)
    E["share"] = E["hook_out"] + 0.3

    # 2. share: posts fly out of the phone on the stressed words
    E["card_tem"] = max(wt("l2", 2), E["share"] + 0.25)  # partage
    E["card_ver"] = max(wt("l2", 5), E["card_tem"] + 0.4)  # Dieu
    E["card_pho"] = max(wt("l2", 9), E["card_ver"] + 0.4)  # vie
    E["screen_publish"] = min(E["card_ver"] + 0.2, E["hook_out"] + 3.4)
    E["publish_in"] = E["card_pho"] + 0.15
    E["publish_tap"] = E["card_pho"] + 0.45
    E["share_out"] = max(E["publish_tap"] + 0.2, end("l2") + 0.05)
    E["pray"] = E["share_out"] + 0.35

    # 3. pray: a hard time, the community prays
    V["l3"] = after("l2", E["pray"] - 0.1)
    E["w_prie"], E["w_porte"] = E["pray"], E["pray"] + 0.4
    E["chips"] = max(wt("l3", 0), E["pray"] + 0.1) + 0.02
    E["chip_pick"] = max(wt("l3", 2), E["chips"] + 0.35)  # dur ?
    E["confier_tap"] = E["chip_pick"] + 0.3
    E["card_maman"] = E["confier_tap"] + 0.12
    E["jeprie_tap"] = max(E["card_maman"] + 0.4, wt("l3", 7))  # prient
    E["upd1"] = E["jeprie_tap"] + 0.3
    E["upd2"] = E["jeprie_tap"] + 0.62
    E["count_end"] = max(end("l3"), E["upd2"]) + 0.05
    E["flip"] = max(E["upd2"] + 0.3, end("l3"))
    E["answer"] = E["flip"] + 0.4

    # 4. answered: "Dieu répond" lands the stamp, "on célèbre" brings the comments
    V["l4"] = after("l3", E["flip"] + 0.2)
    E["notif"] = E["answer"] + 0.15
    E["w_dieu"] = max(wt("l4", 2), E["answer"])
    E["w_repond"] = max(wt("l4", 3), E["w_dieu"] + 0.2)
    E["stamp"] = max(E["w_repond"] + 0.12, E["answer"] + 0.5)
    E["celebrate"] = max(wt("l4", 5), E["stamp"] + 0.3)
    E["answer_out"] = max(E["celebrate"] + 0.95, end("l4") + 0.05, E["notif"] + 1.2)
    E["groups"] = E["answer_out"] + 0.45

    # 5. groups: rows light up when named
    V["l5"] = after("l4", E["answer_out"] + 0.3)
    E["rows"] = max(wt("l5", 0), E["groups"] + 0.05)
    E["hl1"] = max(wt("l5", 3), E["rows"] + 0.45)  # louange
    E["hl2"] = max(wt("l5", 4), E["hl1"] + 0.3)  # étude biblique
    E["hl3"] = max(wt("l5", 6), E["hl2"] + 0.3)  # jeunes
    E["groups_out"] = max(E["hl3"] + 0.45, end("l5") - 0.05)
    E["verse"] = E["groups_out"] + 0.4

    # 6. verse of the day: sunrise
    E["sunrise"] = E["verse"] - 0.2
    V["l6"] = after("l5", E["verse"])
    E["w_matin"] = max(wt("l6", 0) - 0.05, E["verse"] + 0.1)  # "Chaque matin," rises with the words
    E["verse_card"] = max(wt("l6", 2) - 0.25, E["verse"] + 0.3)
    E["verse_text"] = max(wt("l6", 3), E["verse_card"] + 0.3)
    E["verse_ref"] = E["verse_text"] + 0.8
    E["verse_out"] = max(end("l6") + 0.2, E["verse_ref"] + 0.35)
    # the drop lands on a beat of the synthesized bed (an imported track is cut to fit it)
    E["quiz"] = round(E["verse_out"] + 0.35, 3) if music else _ceil_beat(E["verse_out"] + 0.35)

    # 7. quiz on the sky
    V["l7"] = after("l6", E["quiz"] + 0.15)
    E["count"] = E["quiz"]
    E["quiz_title"] = max(wt("l7", 1), E["quiz"] + 0.3)
    E["panel"] = max(E["quiz"] + 1.15, wt("l7", 4))  # niveau
    E["tap"] = E["panel"] + 0.7
    E["correct"] = E["tap"] + 0.45
    E["exact"] = E["correct"] + 0.25
    E["stars"] = E["exact"] + 0.4
    E["quiz_out"] = max(E["stars"] + 0.7, end("l7") + 0.2)
    E["end"] = E["quiz"] + math.ceil((E["quiz_out"] + 0.3 - E["quiz"]) / grid - 1e-6) * grid  # on the beat

    # 8. end card: "RISE" is said as the letters rise
    V["l8"] = after("l7", E["end"] + 0.15)
    E["end_letters"] = E["end"] + 0.15
    E["end_land"] = max(wt("l8", 0) + 0.1, E["end_letters"] + 0.45)
    E["slogan1"], E["slogan2"], E["stores"] = wt("l8", 1), wt("l8", 2), wt("l8", 3)
    E["phones"] = E["stores"] + 0.5
    duration = math.ceil(max(end("l8") + 1.3, E["phones"] + 1.5) * 2) / 2
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
    c = [
        (E["spark"], "spark", 0.8), (E["w_foi"] - 0.04, "hit", 0.7), (E["w_vit"] - 0.05, "swish", 0.6),
        (E["w_ensemble"], "confetti", 0.45), (E["w_ensemble"] + 0.05, "shimmer", 0.5),
        (E["collapse"] - 0.25, "suck", 0.7), (E["letters"], "whoosh", 0.55), (E["logo_land"], "impact", 1.0),
        (E["logo_land"] + 0.02, "chime", 0.45), (E["hook_out"], "whoosh_up", 0.8),
        # share
        (E["share"] + 0.05, "hit", 0.5),
        (E["card_tem"] - 0.06, "pop", 0.7), (E["card_tem"] - 0.1, "swish", 0.45),
        (E["card_ver"] - 0.06, "pop2", 0.7), (E["card_ver"] - 0.1, "swish", 0.45),
        (E["card_pho"] - 0.06, "pop3", 0.7), (E["card_pho"] + 0.05, "shutter", 0.7),
        (E["screen_publish"], "tick", 0.5), (E["publish_in"], "pop", 0.6), (E["publish_tap"], "click", 0.9),
        (E["share_out"], "whoosh_up", 0.9),
        # pray
        (E["w_prie"], "hit", 0.8), (E["w_porte"] - 0.03, "swish", 0.55),
    ]
    for i in range(6):
        c.append((E["chips"] + i * 0.05, "pop" if i % 2 == 0 else "pop2", 0.4))
    c += [
        (E["chip_pick"], "click", 0.7), (E["confier_tap"], "click", 0.9),
        (E["card_maman"], "whoosh", 0.6), (E["jeprie_tap"], "click", 0.9),
    ]
    for i in range(10):
        c.append((E["jeprie_tap"] + 0.1 + i * 0.1, "pop3" if i % 2 else "pop", 0.3))
    c += [(E["jeprie_tap"] + 0.1, "count_roll", 0.5), (E["upd1"], "ding", 0.55), (E["upd2"], "ding2", 0.55),
          (E["flip"], "flip", 0.8)]
    # answer: the stamp on "répond", the comments on "célèbre"
    c += [
        (E["answer"] + 0.05, "swish", 0.55), (E["notif"], "ding", 0.6),
        (E["stamp"], "stamp", 1.0), (E["stamp"] + 0.04, "shimmer", 0.6), (E["stamp"] + 0.02, "confetti", 0.6),
        (E["celebrate"], "confetti", 0.5),
        (E["celebrate"] + 0.05, "pop", 0.55), (E["celebrate"] + 0.35, "pop2", 0.55), (E["celebrate"] + 0.65, "pop3", 0.55),
        (E["answer_out"] - 0.1, "whoosh_long", 0.8), (E["groups"], "impact_soft", 0.6),
    ]
    # groups
    c += [(E["groups"] + 0.05, "swish", 0.5)]
    for i in range(5):
        c.append((E["rows"] + i * 0.09, "tick", 0.45))
    c += [(E["hl1"], "pop", 0.65), (E["hl2"], "pop2", 0.65), (E["hl3"], "pop3", 0.65),
          (E["groups_out"], "whoosh_fast", 0.85)]
    # verse
    c += [(E["sunrise"] + 0.2, "shimmer", 0.45), (E["verse"] + 0.4, "swish", 0.45), (E["verse_card"], "whoosh", 0.55),
          (E["verse_text"], "shimmer", 0.35), (E["verse_ref"], "chime", 0.3), (E["verse_out"], "whoosh_long", 0.6)]
    # quiz (drop)
    c += [(E["count"], "impact", 0.9), (E["count"] + 0.02, "count_roll", 0.6), (E["count"] + 0.95, "pop", 0.6),
          (E["quiz_title"], "swish", 0.5), (E["panel"], "whoosh", 0.6)]
    for i in range(5):
        c.append((E["panel"] + 0.15 + i * 0.09, "tick", 0.45))
    c += [(E["tap"], "click", 0.9), (E["correct"], "success", 0.7), (E["exact"], "whoosh_up", 0.55),
          (E["stars"], "pop", 0.6), (E["stars"] + 0.15, "pop2", 0.6), (E["stars"] + 0.3, "pop3", 0.65),
          (E["stars"] + 0.05, "confetti", 0.55), (E["quiz_out"], "whoosh_up", 0.9)]
    # end
    c += [(E["end_letters"], "whoosh", 0.5), (E["end_land"], "impact", 0.9), (E["end_land"] + 0.02, "chime", 0.5),
          (E["slogan1"] - 0.03, "swish", 0.45), (E["slogan2"] - 0.03, "swish", 0.45), (E["slogan2"] + 0.1, "shimmer", 0.4),
          (E["stores"], "pop", 0.4), (E["phones"], "whoosh_up", 0.45), (DURATION - 1.4, "shimmer", 0.3)]
    return sorted(c)


if __name__ == "__main__":
    print(f"duration {DURATION}s")
    for k in LINES:
        print(f"{k}: {VO_START[k]:6.2f} -> {VO_START[k] + VO_DUR[k]:6.2f}   {LINES[k][1][:50]}")
    print({k: E[k] for k in S})
