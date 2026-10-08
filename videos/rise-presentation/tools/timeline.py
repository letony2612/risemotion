"""Single source of truth for the RISE video timing (120 BPM, 1 beat = 0.5 s).

build.py injects these times into index.html, sfx.py renders the sound
design from CUES and compose_music.py follows the same sections, so picture,
sound effects and music can never drift apart. To swap in a new voice-over,
replace the files in assets/vo/, adjust VO starts if needed and rebuild.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BPM = 120
DURATION = 40.0

# Scene boundaries (every scene change lands on a bar line).
S = {
    "hook": 0.0,
    "share": 4.0,
    "pray": 10.0,
    "answer": 14.0,
    "groups": 18.0,
    "chat": 22.0,
    "verse": 24.0,
    "quiz": 28.0,
    "end": 34.0,
}

# Voice-over lines: (start, text spoken by the TTS, text displayed in captions).
VO = {
    "l1": (0.35, "La foi, ça se vit ensemble.", "La foi, ça se vit ensemble."),
    "l2": (4.45, "Sur Raïze, partage ce que Dieu fait dans ta vie : un témoignage, un verset, une photo.",
           "Sur RISE, partage ce que Dieu fait dans ta vie : un témoignage, un verset, une photo."),
    "l3": (10.35, "Confie une demande : tes frères et sœurs prient pour toi…",
           "Confie une demande : tes frères et sœurs prient pour toi…"),
    "l4": (14.35, "et vous célébrez ensemble quand elle est exaucée.",
           "…et vous célébrez ensemble quand elle est exaucée."),
    "l5": (18.25, "Rejoins des groupes de louange, d'étude biblique, de jeunes…",
           "Rejoins des groupes de louange, d’étude biblique, de jeunes…"),
    "l6": (22.10, "et reste proche de ceux qui comptent.", "…et reste proche de ceux qui comptent."),
    "l7": (24.45, "Chaque matin, une Parole pour ta journée.", "Chaque matin, une Parole pour ta journée."),
    "l8": (28.35, "Et chaque jour, un niveau du quiz biblique, pour parcourir toute la Bible en un an.",
           "Et chaque jour, un niveau du quiz biblique, pour parcourir toute la Bible en un an."),
    "l9": (34.45, "Raïze. Élève-toi. Ensemble. Disponible sur iPhone et Android.",
           "RISE. Élève-toi. Ensemble. Disponible sur iPhone et Android."),
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
# Words shown in amber inside the captions.
KEYWORDS = {"témoignage,", "verset,", "photo.", "prient", "exaucée.", "louange,", "biblique,", "jeunes…",
            "proche", "Parole", "Bible"}


def words():
    """Absolute word timings for every VO line (seconds on the video timeline)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from align import align
    out = {}
    for key, (start, spoken, shown) in VO.items():
        res, _, _ = align(str(ROOT / "assets" / "vo" / f"{key}.wav"), spoken)
        shown_words = []
        for tok in shown.split():
            if shown_words and tok in (":", ";", "!", "?", "»"):
                shown_words[-1] += " " + tok
            else:
                shown_words.append(tok)
        assert len(shown_words) == len(res), (key, len(shown_words), len(res))
        out[key] = [{"w": sw, "t": round(start + r["start"], 3), "e": round(start + r["end"], 3)}
                    for sw, r in zip(shown_words, res)]
    return out


def events(W):
    """Named moments the animation and the sound design both hang on."""
    w = lambda line, i: W[line][i]["t"]
    E = dict(S)
    E.update({
        # hook
        "spark": 0.05, "w_foi": w("l1", 0), "w_vit": w("l1", 2), "w_ensemble": w("l1", 5),
        "collapse": 2.15, "letters": 2.45, "logo_land": 3.0, "hook_out": 3.7,
        # share
        "card_tem": w("l2", 11), "card_ver": w("l2", 13), "card_pho": w("l2", 15),
        "screen_publish": 7.7, "publish_in": 9.0, "publish_tap": 9.35, "share_out": 9.6,
        # pray
        "w_prie": 10.0, "w_porte": 10.45, "chips": w("l3", 0) + 0.05,
        "chip_pick": w("l3", 0) + 0.5, "confier_tap": w("l3", 0) + 0.95, "card_maman": w("l3", 0) + 1.08,
        "jeprie_tap": max(w("l3", 3) + 0.25, w("l3", 0) + 1.55), "count_end": w("l3", 9) + 0.25,
        "upd1": w("l3", 7), "upd2": w("l3", 9), "flip": 13.6,
        # answer
        "notif": 14.4, "celebrate": w("l4", 2), "stamp": w("l4", 7), "answer_out": 17.55,
        # groups
        "rows": w("l5", 0), "hl1": w("l5", 4), "hl2": w("l5", 5), "hl3": w("l5", 8), "groups_out": 21.55,
        # chat
        "b1": 22.05, "b2": 22.45, "b3": 22.85, "b4": 23.25, "chat_out": 23.65,
        # verse
        "sunrise": 23.8, "verse_card": w("l7", 2) - 0.25, "verse_text": w("l7", 3), "verse_ref": 26.9,
        "verse_out": 27.6,
        # quiz
        "count": 28.0, "quiz_title": w("l8", 1), "panel": 29.6, "tap": 30.7, "correct": 31.15,
        "exact": 31.45, "stars": 31.95, "tiles": 32.65, "quiz_out": 33.6,
        # end
        "end_letters": 34.15, "end_land": w("l9", 0) + 0.1, "slogan1": w("l9", 1), "slogan2": w("l9", 2),
        "stores": w("l9", 3), "phones": 36.9,
    })
    return {k: round(v, 3) for k, v in E.items()}


def cues(E, W):
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
        c.append((E["chips"] + i * 0.07, "pop" if i % 2 == 0 else "pop2", 0.42))
    c += [
        (E["chip_pick"], "click", 0.7), (E["chip_pick"] + 0.05, "swish", 0.35), (E["confier_tap"], "click", 0.9),
        (E["card_maman"], "whoosh", 0.6), (E["jeprie_tap"], "click", 0.9),
    ]
    for i in range(10):
        c.append((E["jeprie_tap"] + 0.1 + i * 0.12, "pop3" if i % 2 else "pop", 0.3))
    c += [(E["jeprie_tap"] + 0.1, "count_roll", 0.5), (E["upd1"], "ding", 0.55), (E["upd2"], "ding2", 0.55),
          (E["flip"], "flip", 0.8)]
    # answer
    c += [
        (E["answer"] + 0.05, "swish", 0.55), (E["notif"], "ding", 0.6), (E["celebrate"], "confetti", 0.5),
        (E["celebrate"] + 0.05, "pop", 0.55), (E["celebrate"] + 0.45, "pop2", 0.55), (E["celebrate"] + 0.85, "pop3", 0.55),
        (E["notif"] + 1.5, "swish", 0.4),
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
    c += [(E["sunrise"] + 0.2, "shimmer", 0.45), (E["verse"] + 0.45, "swish", 0.45), (E["verse_card"], "whoosh", 0.55),
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
          (E["stores"], "pop", 0.4), (E["phones"], "whoosh_up", 0.45), (38.6, "shimmer", 0.3)]
    return sorted(c)


if __name__ == "__main__":
    import json
    W = words()
    E = events(W)
    print(json.dumps(E, indent=1))
    for k, ws in W.items():
        print(k, " ".join(f"{x['w']}@{x['t']}" for x in ws))
