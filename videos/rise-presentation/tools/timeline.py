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
MAX_DURATION = 46.0  # the script: 40 to 45 s
MUSIC = ROOT / "assets" / "audio" / "music_track.json"  # an imported track (tools/import_music.py)

# Voice-over lines: (text as spoken, text shown in the captions). Same number of words in both.
LINES = {
    "l1": ("Tu cherches un endroit pour partager ta foi, rencontrer d'autres chrétiens et grandir ?",
           "Tu cherches un endroit pour partager ta foi, rencontrer d'autres chrétiens et grandir ?"),
    "l2": ("Et si je te présentais RISE ?", "Et si je te présentais RISE ?"),
    "l3": ("Ici, tout commence sur le fil d'actu : une question, un témoignage, une réflexion… et on s'encourage dans la foi !",
           "Ici, tout commence sur le fil d'actu : une question, un témoignage, une réflexion… et on s'encourage dans la foi !"),
    "l4": ("Et quand un sujet te touche, va plus loin : rejoins des groupes avec des chrétiens qui ont les mêmes passions que toi.",
           "Et quand un sujet te touche, va plus loin : rejoins des groupes avec des chrétiens qui ont les mêmes passions que toi."),
    "l5": ("Et parce qu'une communauté, c'est aussi se porter les uns les autres… partage tes sujets de prière, prie pour ceux des autres : on n'est pas appelés à avancer seuls.",
           "Et parce qu'une communauté, c'est aussi se porter les uns les autres… partage tes sujets de prière, prie pour ceux des autres : on n'est pas appelés à avancer seuls."),
    "l6": ("Et pour grandir chaque jour dans la Parole, teste ce que tu sais avec les kwiz… et découvre la Bible autrement !",
           "Et pour grandir chaque jour dans la Parole, teste ce que tu sais avec les quiz… et découvre la Bible autrement !"),
    "l7": ("Partager, échanger, prier, apprendre… et grandir ensemble : c'est ça, RISE, le réseau social pensé pour les chrétiens !",
           "Partager, échanger, prier, apprendre… et grandir ensemble : c'est ça, RISE, le réseau social pensé pour les chrétiens !"),
    "l8": ("Rejoins-nous : télécharge RISE gratuitement sur l'App Store et Google Play !",
           "Rejoins-nous : télécharge RISE gratuitement sur l'App Store et Google Play !"),
}

# Captions in two tiers, as in a social ad: a small setup label, then the punch line, which lands on
# its first word. (line, setup word range or None, punch word ranges swapped in place one by one)
BEATS = [
    ("l1", (0, 4), [(5, 7), (8, 10), (11, 12)]),
    ("l2", (0, 4), []),  # the RISE logo lights up on its word
    ("l3", (0, 6), [(7, 8), (9, 10), (11, 12)]),
    ("l3", None, [(13, 18)]),
    ("l4", (0, 5), [(6, 8)]),
    ("l4", (9, 11), [(12, 14)]),
    ("l4", (15, 17), [(18, 21)]),
    ("l5", (0, 3), [(4, 7), (8, 11)]),
    ("l5", (12, 16), [(17, 21)]),
    ("l5", (22, 24), [(25, 28)]),
    ("l6", (0, 4), [(5, 7)]),
    ("l6", (8, 12), [(13, 15)]),
    ("l6", (16, 17), [(18, 20)]),
    ("l7", None, [(0, 0), (1, 1), (2, 2), (3, 3)]),
    ("l7", None, [(4, 6)]),
    ("l7", (7, 9), [(10, 12), (13, 16)]),
    ("l8", (0, 0), [(1, 3)]),
    ("l8", (4, 9), []),  # the store badges carry it
]
PUNCH_TEXT = {}  # (line, first word) -> text shown instead of the words (same timing)


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
    V["l1"] = 0.25
    for a, b in zip(keys, keys[1:]):
        V[b] = end(a) + gap[a]

    # 1. intro: three cards of the app float in on their words, then the RISE logo lights up
    E["hook"] = 0.0
    E["c_share"], E["c_meet"], E["c_grow"] = wt("l1", 5), wt("l1", 8), wt("l1", 11)
    E["intro_back"] = V["l2"]
    E["logo_land"] = wt("l2", 5)  # RISE
    E["splash2"] = E["logo_land"] - 0.85  # the logo animation: its letters burst out 0.85 s in
    E["phone_in"] = max(V["l3"] - 0.3, E["logo_land"] + 0.5)
    # 2. the feed: a question, a testimony, a reflection lift out; everybody encourages
    E["share"] = V["l3"]
    E["q_feed"], E["t_feed"], E["r_feed"] = wt("l3", 7), wt("l3", 9), wt("l3", 11)
    E["enc"] = wt("l3", 13)
    # 3. groups: the tab is tapped on "va plus loin", the groups lift, their members talk
    E["groups_tap"] = wt("l4", 6) - 0.12
    E["groups"] = E["groups_tap"] + 0.12
    E["rows"] = wt("l4", 9)
    E["chat"] = wt("l4", 12)
    E["chat_end"] = end("l4")
    # 4. prayer: the tab, a request lifts, the sheet to share one, then praying for others
    E["pray_tap"] = V["l5"] - 0.05
    E["pray"] = E["pray_tap"] + 0.12
    E["lift_prayer"] = wt("l5", 7)  # porter
    E["sheet_up"] = wt("l5", 12)  # partage
    E["confier"] = wt("l5", 16)  # prière
    E["jeprie"] = wt("l5", 17)  # prie pour ceux des autres
    E["stamp"] = E["jeprie"]
    E["upd1"] = wt("l5", 22)  # on n'est pas appelés à avancer seuls
    E["upd2"] = E["upd1"] + 0.3
    E["answer"] = E["upd1"]
    # 5. quiz: Explorer, the verse, then "teste" starts a quiz as the music drops
    E["explore_tap"] = V["l6"] - 0.05
    E["verse"] = E["explore_tap"] + 0.12
    E["verse_lift"] = wt("l6", 7)  # Parole
    E["quiz"] = wt("l6", 8) - 0.05  # teste
    E["q_tap"] = wt("l6", 13)  # avec
    E["q_ok"] = wt("l6", 15) + 0.05  # quiz
    E["learn"] = wt("l6", 16)  # et découvre la Bible autrement
    # 6. recap and call to action
    E["end"] = V["l7"] - 0.12
    E["v1"], E["v2"], E["v3"], E["v4"] = (wt("l7", i) for i in range(4))
    E["together"] = wt("l7", 4)
    E["w_rise9"] = wt("l7", 9)
    E["splash9"] = E["w_rise9"] - 0.85
    E["dl"] = wt("l8", 1)
    E["free"] = wt("l8", 3)
    E["appstore"], E["gplay"] = wt("l8", 5), wt("l8", 8)
    E["stores"] = E["appstore"]
    duration = math.ceil((end("l8") + 1.3) * 10) / 10
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
    """Sound design cue sheet: (time, sound, gain). No sparkle or bell sounds (shimmer, chime, success):
    not liked, and bells sit right in the voice's band."""
    c = []
    # captions: a light tick when a setup label lands, a swish under each punch line
    for line, setup, punches in BEATS:
        if setup:
            c.append((W[line][setup[0]]["t"] - 0.03, "tick", 0.3))
        for a, _ in punches:
            c.append((W[line][a]["t"] - 0.03, "swish", 0.35))
    # 1. intro
    c += [(E["c_share"], "pop", 0.5), (E["c_meet"], "pop2", 0.5), (E["c_grow"], "pop3", 0.5),
          (E["intro_back"], "whoosh_long", 0.4), (E["logo_land"] - 0.08, "impact_soft", 0.55), (E["phone_in"], "whoosh_up", 0.6)]
    # 2. feed
    c += [(E["q_feed"], "pop", 0.45), (E["t_feed"], "pop2", 0.5), (E["r_feed"], "whoosh", 0.45), (E["r_feed"] + 0.05, "pop3", 0.45),
          (E["enc"], "confetti", 0.5), (E["enc"] + 0.1, "pop", 0.45), (E["enc"] + 0.3, "pop2", 0.45), (E["enc"] + 0.5, "pop3", 0.45)]
    # 3. groups
    c += [(E["groups_tap"], "click", 0.8), (E["groups"], "whoosh_fast", 0.55)]
    for i in range(4):
        c.append((E["rows"] + i * 0.09, "tick", 0.4))
    c += [(E["chat"], "msg_in", 0.55), (E["chat"] + 0.45, "msg_in", 0.5), (E["chat"] + 0.9, "msg_out", 0.5)]
    # 4. prayer
    c += [(E["pray_tap"], "click", 0.8), (E["pray"], "whoosh_fast", 0.55), (E["lift_prayer"], "pop", 0.5),
          (E["sheet_up"], "whoosh", 0.5), (E["confier"], "click", 0.8), (E["jeprie"], "click", 0.85),
          (E["jeprie"] + 0.1, "count_roll", 0.45), (E["upd1"], "msg_in", 0.55), (E["upd2"], "msg_in", 0.5)]
    # 5. quiz (drop)
    c += [(E["explore_tap"], "click", 0.8), (E["verse"], "whoosh_fast", 0.5), (E["verse_lift"], "pop", 0.45),
          (E["quiz"] - 0.08, "impact", 0.65), (E["q_tap"], "click", 0.85), (E["q_ok"], "pop2", 0.6),
          (E["learn"], "whoosh_up", 0.5), (E["learn"] + 0.1, "confetti", 0.5)]
    # 6. recap and end
    c += [(E["end"], "whoosh", 0.55)]
    for k, name in (("v1", "pop"), ("v2", "pop2"), ("v3", "pop3"), ("v4", "pop")):
        c.append((E[k], name, 0.6))
    # the hits land a hair before the word they underline, so the word itself stays clear
    c += [(E["together"], "suck", 0.5), (E["w_rise9"] - 0.08, "impact", 0.6), (E["free"], "impact_soft", 0.5),
          (E["appstore"], "pop", 0.5), (E["gplay"], "pop2", 0.5)]
    return sorted(c)


if __name__ == "__main__":
    print(f"duration {DURATION}s")
    for k in LINES:
        print(f"{k}: {VO_START[k]:6.2f} -> {VO_START[k] + VO_DUR[k]:6.2f}   {LINES[k][1][:50]}")
    print({k: E[k] for k in S})
