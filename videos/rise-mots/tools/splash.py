"""The RISE logo animation for the end card, on black as in the app: the app's own splash
(RISE_presentation/5_logo_anime) in its own colours, white letters and the orange flame. Cropped to the logo
and its glow (the crop of videos/rise-presentation/tools/prepare_splash.py, so the logo sits where it did) and
written with its alpha as VP9 WebM, which the composition plays as an ordinary video clip.
Usage: python3 tools/splash.py  -> assets/brand/rise_splash_dark.webm
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parents[1] / "RISE_presentation" / "5_logo_anime" / "RISE_splash_v1_transparent_1920x1080.mov"
OUT = ROOT / "assets" / "brand" / "rise_splash_dark.webm"
X0, Y0, CW, CH = 480, 220, 960, 500  # the logo and its glow over the whole animation


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-vf", f"crop={CW}:{CH}:{X0}:{Y0}", "-an",
                    "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "18", "-row-mt", "1",
                    "-auto-alt-ref", "0", str(OUT)], check=True)
    print(f"{OUT.relative_to(ROOT)}: {CW}x{CH}")


if __name__ == "__main__":
    main()
