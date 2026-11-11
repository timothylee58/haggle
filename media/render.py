"""Renders scenes.html frame by frame and encodes the MP4.

uv run --python 3.12 --no-project --with playwright --with imageio-ffmpeg python render.py --stills 2 8 14 20 28 34 39 41
uv run --python 3.12 --no-project --with playwright --with imageio-ffmpeg python render.py            # full video

Every frame is a pure function of time (render(t) in scenes.html), so renders are exact and repeatable.
"""

import argparse
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
CHROME = pathlib.Path.home() / "Library/Caches/ms-playwright/chromium-1254/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
TL = json.loads((HERE / "timeline.json").read_text())

parser = argparse.ArgumentParser()
parser.add_argument("--stills", nargs="*", type=float, help="render PNG stills at these seconds instead of a video")
parser.add_argument("--out", default=str(HERE / "haggle-promo.mp4"))
parser.add_argument("--silent", action="store_true", help="skip the soundtrack")
args = parser.parse_args()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(CHROME), args=["--font-render-hinting=none", "--hide-scrollbars"])
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page.add_init_script(f"window.TL = {json.dumps(TL)};")
    page.goto((HERE / "scenes.html").as_uri())
    page.wait_for_load_state("load")
    page.evaluate("document.fonts.ready")
    page.evaluate("initScenes()")

    if args.stills is not None:
        out_dir = HERE / "stills"
        out_dir.mkdir(exist_ok=True)
        for t in args.stills:
            page.evaluate(f"render({t})")
            path = out_dir / f"t{t:05.1f}.png"
            page.screenshot(path=str(path))
            print(path)
        browser.close()
        sys.exit(0)

    fps, frames = TL["fps"], round(TL["duration"] * TL["fps"])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-"]
    if not args.silent:
        cmd += ["-i", str(HERE / "bgm.wav")]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if not args.silent:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(frames):
        page.evaluate(f"render({n / fps})")
        proc.stdin.write(page.screenshot(type="jpeg", quality=95))
        if n % 100 == 0:
            print(f"frame {n}/{frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    browser.close()
    print(args.out)
