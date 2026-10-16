"""One drawing of Tony in black ink on white paper (tools/cartoon2.py), to get his look right before animating
him again: waving, his phone up with RISE on it.
Usage: python3 tools/character_paper.py  -> renders/tony_paper.png
"""
from pathlib import Path

import cartoon2 as c2
import episode1_v7 as v7  # the pen's draw-on, RISE drawn by hand
import rig
from episode1_v7 import cam

ROOT = Path(__file__).resolve().parents[1]


def main():
    P = rig.tony_pose(face=c2.TONY, head_k=1.33, roll=-3.0)
    P["ex"] = dict(smile=0.45, brow=0.25)
    P["phone"] = dict(cx=420.0, cy=1450.0, w=215.0, h=430.0, angle=-6.0)
    P["arm_r"] = dict(wrist=(430.0, 1600.0), hand="none", elbow=(-0.5, 1), k2=0.6)
    P["arm_l"] = dict(wrist=(925.0, 1075.0), hand="open", ang=-84, spread=0.45, curl=0.1, elbow=(1.0, 0.4))

    def screen(cv, fr):
        cx, cy = fr["P"](0, -0.06)
        v7.draw_rise(cv, "r1", cx, cy, fr["w"] * 0.66, 1.0)
    cv = rig.Canvas(0)
    with cam(1.12, (560.0, 1000.0)):
        c2.draw_tony(cv, "tony", P, screen=screen)
    out = ROOT / "renders" / "tony_paper.png"
    out.parent.mkdir(exist_ok=True)
    c2.picture(cv).save(out)
    print(out)


if __name__ == "__main__":
    main()
