"""Single source of truth for the RISE video timing.

The voice-over drives the edit: each scene starts when its line starts, lines
follow each other with their natural breath (taken from the full take when
assets/vo/take.json exists), and a scene only waits when its picture needs a
beat more. build.py injects these times into index.html, sfx.py renders the
sound design from cues() and compose_music.py follows the same sections, so
picture, sound effects and music cannot drift apart.

To swap the voice: python3 tools/import_voice.py take.mp3 && python3 tools/build.py
"""
import json
import math
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
BPM = 120
BEAT = 60 / BPM

# Voice-over lines: (text as spoken, text shown in the captions). Same number of words in both.
LINES = {
    "l1": ("La foi, ça se vit ensemble !", "La foi, ça se vit ensemble !"),
    "l2": ("Sur RISE, partage ce que Dieu fait dans ta vie : un témoignage, un verset, une photo.",
           "Sur RISE, partage ce que Dieu fait dans ta vie : un témoignage, un verset, une photo."),
    "l3": ("Confie une demande : tes frères et sœurs prient pour toi,",
           "Confie une demande : tes frères et sœurs prient pour toi,"),
    "l4": ("et vous célébrez ensemble quand elle est exaucée !", "et vous célébrez ensemble quand elle est exaucée !"),
    "l5": ("Rejoins des groupes de louange, d'étude biblique, de jeunes,",
           "Rejoins des groupes de louange, d’étude biblique, de jeunes,"),
    "l6": ("et reste proche de ceux qui comptent.", "et reste proche de ceux qui comptent."),
    "l7": ("Chaque matin, une Parole pour ta journée.", "Chaque matin, une Parole pour ta journée."),
    "l8": ("Et chaque jour, un niveau du kwiz biblique pour parcourir toute la Bible en un an !",
           "Et chaque jour, un niveau du quiz biblique pour parcourir toute la Bible en un an !"),
    "l9": ("RISE. Élève-toi. Ensemble ! Disponible sur iPhone et Android.",
           "RISE. Élève-toi. Ensemble ! Disponible sur iPhone et Android."),
}

# Caption chunks: word index ranges (inclusive) per line; l1 and l9 are carried by the big type.
CHUNKS = {
    "l2": [(0, 2), (3, 5), (6, 9), (10, 13), (14, 15)],
    "l3": [(0, 2), (3, 6), (7, 9)],
    "l4": [(0, 2), (3, 3), (4, 7)],
    "l5": [(0, 2), (3, 4), (5, 6), (7, 8)],
    "l6": [(0, 2), (3, 6)],
    "l7": [(0, 1), (2, 3), (4, 6)],
    "l8": [(0, 2), (3, 5), (6, 7), (8, 9), (10, 15)],
}
# Words shown in amber inside the captions (compared without punctuation, lower case).
KEYWORDS = {"témoignage", "verset", "photo", "prient", "exaucée", "louange", "biblique", "jeunes", "proche",
            "parole", "bible"}


def _tokens(text):
    out = []
    for tok in text.split():
        if out and tok in (":", ";", "!", "?", "»"):
            out[-1] += " " + tok
        else:
            out.append(tok)
    return out


def _natural_gaps():
    take = ROOT / "assets" / "vo" / "take.json"
    keys = list(LINES)
    gaps = {k: 0.3 for k in keys}
    if take.exists():
        t = json.loads(take.read_text())
        for a, b in zip(keys, keys[1:]):
            gaps[a] = max(0.08, t[b]["start"] - t[a]["end"])
    return gaps


def _ceil_beat(t):
    return math.ceil(t / BEAT - 1e-6) * BEAT


def _plan():
    from align import align
    dur, rel = {}, {}
    for k, (spoken, shown) in LINES.items():
        f = ROOT / "assets" / "vo" / f"{k}.wav"
        dur[k] = sf.info(str(f)).duration
        words, _, _ = align(str(f), spoken)
        shown_words = _tokens(shown)
        assert len(words) == len(shown_words), (k, len(words), len(shown_words))
        rel[k] = [(sw, w["start"], w["end"]) for sw, w in zip(shown_words, words)]
    gap = _natural_gaps()
    V, E = {}, {}
    wt = lambda k, i: V[k] + rel[k][i][1]
    end = lambda k: V[k] + dur[k]

    # 1. hook: the flame, the words, the logo (its own choreography)
    V["l1"] = 0.35
    E["hook"] = 0.0
    E["spark"] = 0.05
    E["w_foi"], E["w_vit"], E["w_ensemble"] = wt("l1", 0), wt("l1", 2), wt("l1", 5)
    E["collapse"] = max(E["w_ensemble"] + 0.7, 2.1)
    E["letters"] = E["collapse"] + 0.3
    E["logo_land"] = E["letters"] + 0.55
    E["hook_out"] = E["logo_land"] + 0.7
    E["share"] = E["hook_out"] + 0.3

    # 2. share: posts fly out of the phone on the words
    V["l2"] = E["share"] + 0.35
    E["card_tem"], E["card_ver"], E["card_pho"] = wt("l2", 11), wt("l2", 13), wt("l2", 15)
    E["screen_publish"] = min(E["card_tem"] + 0.4, E["hook_out"] + 3.4)
    E["publish_in"] = E["card_pho"] + 0.15
    E["publish_tap"] = E["card_pho"] + 0.45
    E["share_out"] = max(E["publish_tap"] + 0.2, end("l2") + 0.05)
    E["pray"] = E["share_out"] + 0.35

    # 3. pray: entrust a request, the community prays
    V["l3"] = max(E["pray"] + 0.1, end("l2") + gap["l2"])
    E["w_prie"], E["w_porte"] = E["pray"], E["pray"] + 0.4
    E["chips"] = wt("l3", 0) + 0.02
    E["chip_pick"] = max(wt("l3", 2), E["chips"] + 0.35)
    E["confier_tap"] = E["chip_pick"] + 0.3
    E["card_maman"] = E["confier_tap"] + 0.12
    E["jeprie_tap"] = max(E["card_maman"] + 0.45, wt("l3", 3))
    E["upd1"] = E["jeprie_tap"] + 0.35
    E["upd2"] = E["jeprie_tap"] + 0.75
    E["count_end"] = max(end("l3"), E["upd2"]) + 0.05
    E["flip"] = max(E["upd2"] + 0.35, end("l3"))
    E["answer"] = E["flip"] + 0.4

    # 4. answered: notification, celebration, the stamp on "exaucée"
    V["l4"] = max(E["answer"] + 0.12, end("l3") + gap["l3"])
    E["notif"] = E["answer"] + 0.3
    E["celebrate"] = wt("l4", 2)
    E["stamp"] = wt("l4", 7)
    E["answer_out"] = max(E["stamp"] + 0.6, end("l4") + 0.05, E["notif"] + 1.3)
    E["groups"] = E["answer_out"] + 0.45

    # 5. groups: rows light up when named
    V["l5"] = max(E["groups"] + 0.2, end("l4") + gap["l4"])
    E["rows"] = wt("l5", 0)
    E["hl1"], E["hl2"], E["hl3"] = wt("l5", 4), wt("l5", 5), wt("l5", 8)
    E["groups_out"] = max(E["hl3"] + 0.4, end("l5") - 0.05)
    E["chat"] = E["groups_out"] + 0.4

    # 6. chat: messages arrive
    V["l6"] = max(E["chat"] + 0.05, end("l5") + gap["l5"])
    E["b1"] = E["chat"] + 0.05
    E["b2"], E["b3"], E["b4"] = E["b1"] + 0.36, E["b1"] + 0.72, E["b1"] + 1.08
    E["chat_out"] = max(E["b4"] + 0.45, end("l6"))
    E["verse"] = E["chat_out"] + 0.35

    # 7. verse of the day: sunrise
    E["sunrise"] = E["verse"] - 0.2
    V["l7"] = max(E["verse"] + 0.35, end("l6") + gap["l6"])
    E["verse_card"] = wt("l7", 2) - 0.25
    E["verse_text"] = wt("l7", 3)
    E["verse_ref"] = E["verse_text"] + 0.8
    E["verse_out"] = max(end("l7") + 0.25, E["verse_ref"] + 0.35)
    E["quiz"] = _ceil_beat(E["verse_out"] + 0.4)  # the drop lands on a beat

    # 8. quiz on the sky
    V["l8"] = max(E["quiz"] + 0.25, end("l7") + gap["l7"])
    E["count"] = E["quiz"]
    E["quiz_title"] = wt("l8", 1)
    E["panel"] = max(E["quiz"] + 1.3, wt("l8", 3))
    E["tap"] = E["panel"] + 1.0
    E["correct"] = E["tap"] + 0.45
    E["exact"] = E["correct"] + 0.3
    E["stars"] = E["exact"] + 0.5
    E["tiles"] = E["stars"] + 0.55
    E["quiz_out"] = max(E["tiles"] + 0.8, end("l8") + 0.2)
    E["end"] = _ceil_beat(E["quiz_out"] + 0.4)

    # 9. end card
    V["l9"] = E["end"] + 0.4
    E["end_letters"] = E["end"] + 0.15
    E["end_land"] = max(wt("l9", 0) + 0.1, E["end_letters"] + 0.45)
    E["slogan1"], E["slogan2"], E["stores"] = wt("l9", 1), wt("l9", 2), wt("l9", 3)
    E["phones"] = E["stores"] + 0.5
    duration = math.ceil(max(end("l9") + 1.8, E["phones"] + 1.8) * 2) / 2

    W = {k: [{"w": sw, "t": round(float(V[k] + a), 3), "e": round(float(V[k] + b), 3)} for sw, a, b in rel[k]] for k in LINES}
    E = {k: round(float(v), 3) for k, v in E.items()}
    V = {k: round(float(v), 3) for k, v in V.items()}
    return E, V, W, duration, dur


E, VO_START, W, DURATION, VO_DUR = _plan()
S = {k: E[k] for k in ("hook", "share", "pray", "answer", "groups", "chat", "verse", "quiz", "end")}


def words():
    return W


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
    # answer
    c += [
        (E["answer"] + 0.05, "swish", 0.55), (E["notif"], "ding", 0.6), (E["celebrate"], "confetti", 0.5),
        (E["celebrate"] + 0.05, "pop", 0.55), (E["celebrate"] + 0.35, "pop2", 0.55), (E["celebrate"] + 0.65, "pop3", 0.55),
        (E["stamp"], "stamp", 1.0), (E["stamp"] + 0.04, "shimmer", 0.6), (E["stamp"] + 0.02, "confetti", 0.6),
        (E["answer_out"] - 0.1, "whoosh_long", 0.8), (E["groups"], "impact_soft", 0.6),
    ]
    # groups
    c += [(E["groups"] + 0.05, "swish", 0.5)]
    for i in range(5):
        c.append((E["rows"] + i * 0.09, "tick", 0.45))
    c += [(E["hl1"], "pop", 0.65), (E["hl2"], "pop2", 0.65), (E["hl3"], "pop3", 0.65),
          (E["groups_out"], "whoosh_fast", 0.85)]
    # chat
    c += [(E["chat"] + 0.03, "swish", 0.5), (E["b1"], "msg_in", 0.7), (E["b2"], "msg_out", 0.7),
          (E["b3"], "msg_in", 0.7), (E["b4"], "msg_out", 0.7), (E["chat_out"], "whoosh_up", 0.7)]
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
          (E["stars"] + 0.05, "confetti", 0.55), (E["tiles"] - 0.1, "whoosh", 0.5),
          (E["tiles"], "pop", 0.55), (E["tiles"] + 0.15, "pop2", 0.55), (E["tiles"] + 0.3, "pop3", 0.55),
          (E["quiz_out"], "whoosh_up", 0.9)]
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
