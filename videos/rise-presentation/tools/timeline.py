"""Single source of truth for the RISE video timing.

The voice-over drives the edit, as in a social ad: the lines run on one after
the other with only the take's own short breath (capped so the read never
stalls), nothing waits for the picture, and every move is keyed to a word.
Word times come from dtw_align.py (cached in assets/vo/words.json), so captions
and kinetic beats land on the words. build.py injects these times into index.html, sfx.py renders the
sound design from cues() and compose_music.py follows the same sections, so
picture, sound effects and music cannot drift apart.

To swap the voice: python3 tools/import_voice.py take.mp3 && python3 tools/build.py
The English version: RISE_LANG=en python3 tools/import_voice.py take.mp3 && python3 tools/build.py --lang en
(its own lines, captions and word anchors below, its own voice folder and audio beds).
"""
import json
import math
import os
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
LANG = os.environ.get("RISE_LANG", "fr")  # the version being built: "fr", or "en" (build.py --lang en)
SUFFIX = "" if LANG == "fr" else f"_{LANG}"  # the other versions keep their own voice folder and audio beds
VO = ROOT / "assets" / f"vo{SUFFIX}"

# Voice-over lines: (text as spoken, text shown in the captions). Same number of words in both.
_LINES = {"fr": {
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
}, "en": {k: (t, t) for k, t in {
    "l1": "Looking for a place to share your faith, meet other Christians and grow?",
    "l2": "Then let me introduce you to RISE!",
    "l3": "It all starts in the feed: a question, a testimony, a reflection… and we lift each other up in faith!",
    "l4": "And when something speaks to you, go deeper: join groups with Christians who share your passions.",
    "l5": "Because community also means carrying each other… share your prayer requests, pray for others: we were never meant to walk alone.",
    "l6": "And to grow in the Word every day, test what you know with quizzes… and discover the Bible in a whole new way!",
    "l7": "Share, connect, pray, learn… and grow together: that's RISE, the social network made for Christians!",
    "l8": "Join us: download RISE for free on the App Store and Google Play!",
}.items()}}
LINES = _LINES[LANG]

# Captions in two tiers, as in a social ad: a small setup label, then the punch line, which lands on
# its first word. (line, setup word range or None, punch word ranges swapped in place one by one)
_BEATS = {"fr": [
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
], "en": [
    ("l1", (0, 4), [(5, 7), (8, 10), (11, 12)]),
    ("l2", (0, 5), []),
    ("l3", (0, 5), [(6, 7), (8, 9), (10, 11)]),
    ("l3", None, [(12, 19)]),
    ("l4", (0, 5), [(6, 7)]),
    ("l4", (8, 9), [(10, 11)]),
    ("l4", None, [(12, 15)]),
    ("l5", (0, 3), [(4, 6)]),
    ("l5", (7, 10), [(11, 13)]),
    ("l5", (14, 16), [(17, 20)]),
    ("l6", (0, 2), [(3, 7)]),
    ("l6", (8, 11), [(12, 13)]),
    ("l6", (14, 15), [(16, 22)]),
    ("l7", None, [(0, 0), (1, 1), (2, 2), (3, 3)]),
    ("l7", None, [(4, 6)]),
    ("l7", (7, 8), [(9, 11), (12, 14)]),
    ("l8", (0, 1), [(2, 5)]),
    ("l8", (6, 12), []),
]}
BEATS = _BEATS[LANG]
# The words the edit is keyed to: event -> (line, word index[, nudge in seconds]), in each language's own sentences
_ANCHORS = {
    "fr": {"c_share": ("l1", 5), "c_meet": ("l1", 8), "c_grow": ("l1", 11), "logo_land": ("l2", 5),
           "q_feed": ("l3", 7), "t_feed": ("l3", 9), "r_feed": ("l3", 11), "enc": ("l3", 13),
           "groups_tap": ("l4", 6), "rows": ("l4", 9), "chat": ("l4", 12),
           "lift_prayer": ("l5", 7), "sheet_up": ("l5", 12), "confier": ("l5", 16), "jeprie": ("l5", 17), "upd1": ("l5", 22),
           "verse_lift": ("l6", 7), "quiz": ("l6", 8), "q_tap": ("l6", 13), "q_ok": ("l6", 15), "learn": ("l6", 16),
           "together": ("l7", 4), "w_rise9": ("l7", 9), "dl": ("l8", 1), "free": ("l8", 3), "appstore": ("l8", 5), "gplay": ("l8", 8)},
    "en": {"c_share": ("l1", 5), "c_meet": ("l1", 8), "c_grow": ("l1", 11), "logo_land": ("l2", 6),
           "q_feed": ("l3", 6), "t_feed": ("l3", 8), "r_feed": ("l3", 10), "enc": ("l3", 12),
           "groups_tap": ("l4", 6), "rows": ("l4", 8), "chat": ("l4", 10),
           "lift_prayer": ("l5", 4), "sheet_up": ("l5", 7), "confier": ("l5", 10), "jeprie": ("l5", 11), "upd1": ("l5", 14),
           "verse_lift": ("l6", 5), "quiz": ("l6", 8), "q_tap": ("l6", 12), "q_ok": ("l6", 13, 0.25), "learn": ("l6", 14),
           "together": ("l7", 4), "w_rise9": ("l7", 8), "dl": ("l8", 2), "free": ("l8", 5), "appstore": ("l8", 8), "gplay": ("l8", 11)},
}
A = _ANCHORS[LANG]
PUNCH_TEXT = {}  # (line, first word) -> text shown instead of the words (same timing)
HERO = ("l1", "l2")  # the hook: its captions sit large in the middle of the frame, the lead-in typed word by word


def _tokens(text):
    out = []
    for tok in text.split():
        if out and tok in (":", ";", "!", "?", "»"):
            out[-1] += " " + tok
        else:
            out.append(tok)
    return out


def _natural_gaps():
    take = VO / "take.json"
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
    cache_file = VO / "words.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    for k, (spoken, shown) in LINES.items():
        f = VO / f"{k}.wav"
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
    at = lambda name: wt(*A[name][:2]) + (A[name][2] if len(A[name]) > 2 else 0.0)  # an anchor word, plus its nudge
    end = lambda k: V[k] + dur[k]
    keys = list(LINES)
    # the read never waits for the picture: each line follows the previous one after its breath
    V["l1"] = 0.25
    for a, b in zip(keys, keys[1:]):
        V[b] = end(a) + gap[a]

    # 1. hook: the phone is there from the first frame; a card of the app comes out of it on each phrase,
    #    then it dips away and the RISE logo lights up
    E["hook"] = 0.0
    E["c_share"], E["c_meet"], E["c_grow"] = at("c_share"), at("c_meet"), at("c_grow")
    E["intro_back"] = V["l2"]
    E["logo_land"] = at("logo_land")  # RISE
    E["splash2"] = E["logo_land"] - 0.85  # the logo animation: its letters burst out 0.85 s in
    E["phone_in"] = max(V["l3"] - 0.3, E["logo_land"] + 0.5)
    # 2. the feed: a question, a testimony, a reflection lift out; everybody encourages
    E["share"] = V["l3"]
    E["q_feed"], E["t_feed"], E["r_feed"] = at("q_feed"), at("t_feed"), at("r_feed")
    E["enc"] = at("enc")
    # 3. groups: the tab is tapped on "va plus loin", the groups lift, their members talk
    E["groups_tap"] = at("groups_tap") - 0.12
    E["groups"] = E["groups_tap"] + 0.12
    E["rows"] = at("rows")
    E["chat"] = at("chat")
    E["chat_end"] = end("l4")
    # 4. prayer: the tab, a request lifts, the sheet to share one, then praying for others
    E["pray_tap"] = V["l5"] - 0.05
    E["pray"] = E["pray_tap"] + 0.12
    E["lift_prayer"] = at("lift_prayer")  # porter / carrying
    E["sheet_up"] = at("sheet_up")  # partage / share
    E["confier"] = at("confier")  # prière / requests
    E["jeprie"] = at("jeprie")  # prie pour ceux des autres / pray for others
    E["stamp"] = E["jeprie"]
    E["upd1"] = at("upd1")  # on n'est pas appelés à avancer seuls / we were never meant…
    E["upd2"] = E["upd1"] + 0.3
    E["answer"] = E["upd1"]
    # 5. quiz: Explorer, the verse, then "teste" starts a quiz as the music drops
    E["explore_tap"] = V["l6"] - 0.05
    E["verse"] = E["explore_tap"] + 0.12
    E["verse_lift"] = at("verse_lift")  # Parole / Word
    E["quiz"] = at("quiz") - 0.05  # teste / test
    E["q_tap"] = at("q_tap")  # avec / with
    E["q_ok"] = at("q_ok") + 0.05  # quiz / quizzes
    E["learn"] = at("learn")  # et découvre… / and discover…
    # 6. recap and call to action
    E["end"] = V["l7"] - 0.12
    E["v1"], E["v2"], E["v3"], E["v4"] = (wt("l7", i) for i in range(4))
    E["together"] = at("together")
    E["w_rise9"] = at("w_rise9")
    E["splash9"] = E["w_rise9"] - 0.85
    E["dl"] = at("dl")
    E["free"] = at("free")
    E["appstore"], E["gplay"] = at("appstore"), at("gplay")
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


if all((VO / f"{k}.wav").exists() for k in LINES):
    E, VO_START, W, DURATION, VO_DUR = _plan()
else:  # a version without its voice yet: tools/import_voice.py fills VO first
    E, VO_START, W, DURATION, VO_DUR = {}, {}, {}, 0.0, {}
S = {k: E[k] for k in ("hook", "share", "pray", "answer", "groups", "verse", "quiz", "end") if k in E}


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


def cues(E=E, W=W, style=""):
    """Sound design cue sheet: (time, sound, gain). No sparkle or bell sounds (shimmer, chime, success):
    not liked, and bells sit right in the voice's band."""
    if style == "apple":
        return _cues_apple(E, W)
    c = []
    # captions: a light tick when a setup label lands, a swish under each punch line
    for line, setup, punches in BEATS:
        if setup:
            c.append((W[line][setup[0]]["t"] - 0.03, "tick", 0.3))
        for a, _ in punches:
            c.append((W[line][a]["t"] - 0.03, "swish", 0.35))
    # 1. hook: the phone swings in on the first frame, a card comes out of it on each phrase
    c += [(0.0, "whoosh_up", 0.5), (E["c_share"], "pop", 0.5), (E["c_meet"], "pop2", 0.5), (E["c_grow"], "pop3", 0.5),
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


def _cues_apple(E, W):
    """The Apple-style cut (build.py --apple): few sounds, soft and natural, generated for this video
    (assets/sfx_apple): a muted fingertip tap where a finger touches or a card lands, a breath of air when
    the phone, a screen or a sheet moves, one deep soft impact on the logo and on the drop. Nothing under
    the captions and no ticks: too many bright little sounds tired the ear. The air peaks 0.22 s in, the
    impact 0.11 s in."""
    c = []
    # 1. hook: the phone swings in, a card lands on each phrase, the phone dips, RISE, the phone again
    c += [(0.0, "air", 0.45), (E["c_share"] + 0.1, "tap", 0.35), (E["c_meet"] + 0.1, "tap2", 0.35), (E["c_grow"] + 0.1, "tap", 0.35),
          (E["intro_back"] - 0.05, "air", 0.4), (E["logo_land"] - 0.11, "impact", 0.55), (E["phone_in"] - 0.1, "air", 0.5)]
    # 2. feed: the three pieces lift, the comments come in
    c += [(E["q_feed"], "tap2", 0.3), (E["t_feed"], "tap", 0.3), (E["r_feed"], "tap2", 0.3),
          (E["enc"] + 0.1, "tap", 0.25), (E["enc"] + 0.6, "tap2", 0.25)]
    # 3. groups: the tab, the screen, the rows, the messages
    talk = max(0.3, min((E["chat_end"] - E["chat"]) / 4, (E["pray_tap"] - 0.76 - E["chat"]) / 3))
    c += [(E["groups_tap"], "tap", 0.55), (E["groups"] - 0.1, "air", 0.35), (E["rows"] + 0.05, "tap2", 0.25)]
    c += [(E["chat"] + i * talk + 0.05, ("tap2", "tap")[i % 2], 0.25) for i in range(4)]
    # 4. prayer: the tab, the request, the sheet up, "Confier", the sheet down, "Je prie", the replies
    c += [(E["pray_tap"], "tap", 0.55), (E["pray"] - 0.1, "air", 0.35), (E["lift_prayer"], "tap2", 0.3),
          (E["sheet_up"] - 0.1, "air", 0.4), (E["confier"], "tap", 0.55), (E["jeprie"] - 0.35, "air", 0.3),
          (E["jeprie"] + 0.2, "tap", 0.55), (E["upd1"] + 0.05, "tap2", 0.25), (E["upd2"] + 0.05, "tap", 0.25)]
    # 5. explorer, then the quiz on the drop
    c += [(E["explore_tap"], "tap", 0.55), (E["verse"] - 0.1, "air", 0.35), (E["verse_lift"], "tap2", 0.3),
          (E["quiz"] - 0.08, "tap", 0.55), (E["quiz"] - 0.11, "impact", 0.6), (E["q_tap"], "tap", 0.55),
          (E["learn"] - 0.1, "air", 0.35)]
    # 6. recap: the phone drops away, four screens, they gather, the logo, the stores
    c += [(E["end"] - 0.1, "air", 0.5)]
    c += [(E[k] + 0.05, ("tap", "tap2")[i % 2], 0.3) for i, k in enumerate(("v1", "v2", "v3", "v4"))]
    c += [(E["together"] - 0.05, "air", 0.35), (E["w_rise9"] - 0.11, "impact", 0.6),
          (E["appstore"], "tap", 0.35), (E["gplay"], "tap2", 0.35)]
    return sorted(c)


if __name__ == "__main__":
    print(f"duration {DURATION}s")
    for k in LINES:
        print(f"{k}: {VO_START[k]:6.2f} -> {VO_START[k] + VO_DUR[k]:6.2f}   {LINES[k][1][:50]}")
    print({k: E[k] for k in S})
