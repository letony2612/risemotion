"""The app pictures of a translated version, from its captures in RISE_presentation/1_captures_clair_<lang>.

assets/screens_<lang>/  the screens shown whole on the phone
assets/lift_<lang>/     the pieces that lift out of the screen (tools/lifts.py on the translated captures)
assets/ui_<lang>/       the other pieces the film uses: the same boxes as prepare_assets.py, plus the two
                        cut from the clips' frames (1_captures_clair_<lang>/extraits, see tools/retext.py)
build.py --lang <lang> takes a picture from these folders when it is there, the French one otherwise
(the flame, the logo: nothing to translate).
Usage: python3 tools/localize.py --lang en
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LANG = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else os.environ.get("RISE_LANG", "en")
CAP = ROOT.parent.parent / "RISE_presentation" / f"1_captures_clair_{LANG}"
SCREENS = ["02_accueil", "06_priere", "10_groupes", "14_explorer", "15_quiz_parcours", "17_quiz_question"]
UI = {  # the boxes of prepare_assets.py
    "com_david": ("03_post_commentaires", (34, 1255, 1046, 1409)),
    "com_esther": ("03_post_commentaires", (34, 1433, 1046, 1584)),
    "com_rebecca": ("03_post_commentaires", (34, 1609, 1046, 1760)),
    "upd_sarah": ("07_priere_detail", (52, 1159, 1035, 1323)),
    "upd_esther": ("07_priere_detail", (52, 1422, 1035, 1602)),
    "quiz_stats": ("15_quiz_parcours", (40, 308, 1040, 875)),
    "answer_1_sel": ("17_quiz_question", (52, 623, 1029, 770)),
    "answer_1_ok": ("18_quiz_reponse", (52, 623, 1029, 770)),
}


def main():
    screens, ui = ROOT / "assets" / f"screens_{LANG}", ROOT / "assets" / f"ui_{LANG}"
    for d in (screens, ui):
        d.mkdir(parents=True, exist_ok=True)
    for name in SCREENS:
        Image.open(CAP / f"{name}.png").convert("RGBA").save(screens / f"{name}.png")
    for name, (cap, box) in UI.items():
        Image.open(CAP / f"{cap}.png").convert("RGBA").crop(box).save(ui / f"{name}.png")
    for piece in sorted((CAP / "extraits").glob("*.png")):
        shutil.copy(piece, ui / piece.name)
    subprocess.run([sys.executable, str(ROOT / "tools" / "lifts.py"), "--lang", LANG], check=True, capture_output=True)
    print(f"{LANG}: {len(SCREENS)} screens, {len(list(ui.glob('*.png')))} pieces in {ui.name}, lifts in lift_{LANG}")


if __name__ == "__main__":
    main()
