#!/usr/bin/env python3
import random
import shlex
import subprocess
from pathlib import Path

WALLS_DIR = "~/Pictures/walls"


def notify(message):
    try:
        subprocess.run(["notify-send", "wallpaper.py", message], check=False)
    except OSError:
        pass


def main():
    images = [f for f in Path(WALLS_DIR).expanduser().iterdir() if f.is_file()]
    if len(images) < 2:
        return

    img1, img2 = random.sample(images, 2)

    subprocess.run(shlex.split("pkill swaybg"), capture_output=True)

    cmd = f"swaybg -o HDMI-A-1 -i {shlex.quote(str(img1))} -m fill -o eDP-1 -i {shlex.quote(str(img2))} -m fill"
    subprocess.Popen(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    notify("Wallpapers changed.")


if __name__ == "__main__":
    main()
