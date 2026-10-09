"""The RISE logo animation (RISE_presentation/5_logo_anime), made for a light background.

The source has white letters for a dark screen: the letters turn to the logo's ink, the flame and its
glow keep their colours (the more saturated a pixel, the more of it is kept). Cropped to the logo and
written with its alpha as VP9 WebM, which the composition plays as an ordinary video clip.
Usage: python3 tools/prepare_splash.py  -> assets/brand/rise_splash_light.webm
"""
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent.parent / "RISE_presentation" / "5_logo_anime" / "RISE_splash_v1_transparent_1920x1080.mov"
OUT = ROOT / "assets" / "brand" / "rise_splash_light.webm"
W, H = 1920, 1080
X0, Y0, CW, CH = 480, 220, 960, 500  # the logo and its glow over the whole animation
INK = np.array([26, 23, 20], np.float32)


def main():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(SRC), "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 4)[:, Y0:Y0 + CH, X0:X0 + CW].astype(np.float32)
    rgb, alpha = fr[..., :3], fr[..., 3:]
    mx, mn = rgb.max(-1, keepdims=True), rgb.min(-1, keepdims=True)
    keep = np.clip(((mx - mn) / (mx + 1e-6) - 0.08) / 0.25, 0, 1)
    out = np.concatenate([INK * (1 - keep) + rgb * keep, alpha], -1).clip(0, 255).astype(np.uint8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{CW}x{CH}", "-r", "30",
                            "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "18", "-row-mt", "1",
                            "-auto-alt-ref", "0", str(OUT)], stdin=subprocess.PIPE)
    enc.communicate(out.tobytes())
    print(f"{OUT.relative_to(ROOT)}: {len(out)} frames, {CW}x{CH}")


if __name__ == "__main__":
    main()
