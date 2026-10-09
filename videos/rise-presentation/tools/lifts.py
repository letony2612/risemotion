"""Pieces of the app screens that lift out of the phone (cut from the real captures).

Each entry: the capture shown on the phone screen, the piece's box in its 1080x2400 pixels, and an
optional patch painted with the page colour (e.g. a floating button that overlaps the piece).
build.py places every piece exactly over its spot on the screen, so it lifts off its own pixels.
Usage: python3 tools/lifts.py  -> assets/lift/<name>.png
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT.parent.parent / "RISE_presentation" / "1_captures_clair"
OUT = ROOT / "assets" / "lift"
PAGE = (250, 248, 245)

LIFTS = {
    # intro, floating: the composer (sharing), the messages (meeting), the quiz streak is in assets/ui
    "composer": ("04_publier.png", (0, 180, 1080, 975), None),
    "messages": ("12_messages.png", (0, 395, 1080, 1365), None),
    # feed: the prompt ("une question"), Sarah's testimony (the + button painted out)
    "feed_prompt": ("02_accueil.png", (0, 330, 1080, 470), None),
    "post_sarah": ("02_accueil.png", (0, 1596, 1080, 2000), (880, 340, 1080, 404)),
    # groups, and what their members say (floating beside the phone)
    "group_1": ("10_groupes.png", (0, 410, 1080, 576), None),
    "group_2": ("10_groupes.png", (0, 608, 1080, 774), None),
    "group_3": ("10_groupes.png", (0, 803, 1080, 970), None),
    "group_4": ("10_groupes.png", (0, 1001, 1080, 1168), None),
    "chat_caleb": ("11_groupe_discussion.png", (20, 700, 800, 960), None),
    "chat_deborah": ("11_groupe_discussion.png", (20, 975, 800, 1175), None),
    "chat_me": ("11_groupe_discussion.png", (300, 1190, 1060, 1360), None),
    "chat_jonathan": ("11_groupe_discussion.png", (20, 1410, 800, 1610), None),
    # prayers: Rebecca's request for her mother, the sheet to share a request
    "prayer_maman": ("06_priere.png", (40, 349, 1036, 945), None),
    "confier_sheet": ("09_confier_une_priere.png", (0, 720, 1080, 2400), None),
    # explorer: the verse of the day
    "verse": ("14_explorer.png", (40, 215, 1040, 905), None),
    # quiz: the first answer (its states are stacked from assets/ui), the "Exact !" sheet
    "quiz_answer": ("17_quiz_question.png", (52, 623, 1029, 770), None),
    "quiz_exact": ("18_quiz_reponse.png", (0, 1660, 1080, 2330), None),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cap, box, patch) in LIFTS.items():
        im = Image.open(CAP / cap).convert("RGB").crop(box)
        if patch:
            im.paste(PAGE, patch)
        im.save(OUT / f"{name}.png")
        print(name, im.size)


if __name__ == "__main__":
    main()
