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
    # feed: Sarah's testimony ("Dieu est fidèle"), the + button painted out
    "post_sarah": ("02_accueil.png", (0, 1596, 1080, 2000), (880, 340, 1080, 404)),
    # prayers: Rebecca's request for her mother
    "prayer_maman": ("06_priere.png", (40, 349, 1036, 945), None),
    # answered: Sarah's job ("Exaucée")
    "answered": ("08_priere_exaucee.png", (30, 335, 1050, 1020), None),
    # groups named in the voice-over
    "group_1": ("10_groupes.png", (0, 410, 1080, 576), None),
    "group_2": ("10_groupes.png", (0, 608, 1080, 774), None),
    "group_4": ("10_groupes.png", (0, 1001, 1080, 1168), None),
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
