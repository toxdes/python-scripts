#!/usr/bin/env python3
import shlex
import subprocess
import sys


def run(cmd):
    return subprocess.run(shlex.split(cmd), capture_output=True, text=True)


def get_status():
    p = run("playerctl status")
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def get_metadata(field):
    p = run(f"playerctl metadata {field}")
    return p.stdout.strip()


def get_player():
    p = run("playerctl -l")
    out = p.stdout.strip()
    return out.split("\n")[0] if out else ""


def player_icon(player):
    match player:
        case p if "spotify" in p.lower():
            return ""
        case p if "firefox" in p.lower() or "zen-browser" in p.lower():
            return ""
        case p if "mpv" in p.lower():
            return ""
        case _:
            return ""


def main():
    status = get_status()
    if status is None:
        sys.exit(0)

    if status == "Playing":
        play_icon = ""
    elif status == "Paused":
        play_icon = ""
    else:
        sys.exit(0)

    artist = get_metadata("artist")
    title = get_metadata("title")
    player = get_player()

    app_icon = player_icon(player)

    all_text = f"{artist} - {title}"
    max_len = 40
    if len(all_text) > max_len:
        text = all_text[:max_len] + "..."
    else:
        text = all_text

    escaped = text.replace("&", "&amp;")
    print(f"{app_icon} {play_icon}{escaped}")


if __name__ == "__main__":
    main()
