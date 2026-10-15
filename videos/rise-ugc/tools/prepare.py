"""The shots' footage, cut to the frame (1080x1920, 30 fps) and to the length each shot plays (tools/build.py).

- the app (fil, groupe, priere): the real app's screen recordings (RISE_presentation/4_clips, 1080x2400, made on
  a demo database: no real member appears), the middle 1920 rows kept;
- the people (seul, amis, sourire): free stock clips put in footage/ by hand (sources and licence in BRIEF.md),
  scaled to cover the frame, cropped around cx, and given a phone camera's look: a little moving grain.
A shot whose footage is not there yet is skipped (the build leaves it empty and says so).
Usage: python3 tools/prepare.py  -> assets/shots/<id>.mp4
"""
import subprocess

from build import APP, FPS, H, ROOT, TIMED, W


def main():
    out_dir = ROOT / "assets" / "shots"
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in TIMED:
        if not s["src"].exists():
            print(f'{s["id"]:8s} skipped: {s["src"].relative_to(ROOT.parents[1])} is not there yet')
            continue
        if s["src"].parent == APP:
            vf = f"crop={W}:{H}:0:(ih-{H})/2,fps={FPS}"
        else:
            cx = s.get("cx", 0.5)
            vf = (f"scale=w='if(gt(a,{W}/{H}),-2,{W})':h='if(gt(a,{W}/{H}),{H},-2)',crop={W}:{H}:(iw-{W})*{cx}:(ih-{H})/2,"
                  f"fps={FPS},noise=alls=5:allf=t")
        out = out_dir / f'{s["id"]}.mp4'
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["at"]), "-i", str(s["src"]), "-t", f'{s["d"] + 2 / FPS:.3f}',
                        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(out)], check=True)
        print(f'{s["id"]:8s} {s["d"]:.3f}s from {s["src"].name} at {s["at"]}s -> {out.relative_to(ROOT)}')


if __name__ == "__main__":
    main()
