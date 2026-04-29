#!/usr/bin/env python3
import os
import shlex
import subprocess
import sys

DIR = os.path.expanduser("~/.config/rofi/powermenu/type-1")
THEME = "style-1"

shutdown = " Shutdown"
reboot = " Reboot"
lock = " Lock"
suspend = " Suspend"
logout = " Logout"
yes = " Yes"
no = " No"


def run(cmd):
    return subprocess.run(shlex.split(cmd), capture_output=True, text=True)


def rofi_menu(prompt, mesg, options):
    cmd = [
        "rofi", "-dmenu",
        "-p", prompt,
        "-mesg", mesg,
        "-theme", f"{DIR}/{THEME}.rasi",
    ]
    p = subprocess.run(cmd, input="\n".join(options), capture_output=True, text=True)
    return p.stdout.strip()


def confirm_menu():
    cmd = [
        "rofi",
        "-theme-str", "window {location: center; anchor: center; fullscreen: false; width: 250px;}",
        "-theme-str", "mainbox {children: [ \"message\", \"listview\" ];}",
        "-theme-str", "listview {columns: 2; lines: 1;}",
        "-theme-str", "element-text {horizontal-align: 0.5;}",
        "-theme-str", "textbox {horizontal-align: 0.5;}",
        "-dmenu",
        "-p", "Confirmation",
        "-mesg", "Are you Sure?",
        "-theme", f"{DIR}/{THEME}.rasi",
    ]
    p = subprocess.run(cmd, input=f"{yes}\n{no}", capture_output=True, text=True)
    return p.stdout.strip()


def run_cmd(action):
    if confirm_menu() != yes:
        sys.exit(0)

    if action == "--shutdown":
        subprocess.run(shlex.split("systemctl poweroff"))
    elif action == "--reboot":
        subprocess.run(shlex.split("systemctl reboot"))
    elif action == "--suspend":
        subprocess.run(shlex.split("amixer set Master mute"))
        subprocess.run(shlex.split("swaylock -f -c 000000"))
        subprocess.run(shlex.split("systemctl suspend"))
    elif action == "--logout":
        desktop = os.environ.get("DESKTOP_SESSION", "")
        if desktop == "openbox":
            subprocess.run(shlex.split("openbox --exit"))
        elif desktop == "bspwm":
            subprocess.run(shlex.split("bspc quit"))
        elif desktop == "i3":
            subprocess.run(shlex.split("i3-msg exit"))
        elif desktop == "plasma":
            subprocess.run(shlex.split("qdbus org.kde.ksmserver /KSMServer logout 0 0 0"))


def main():
    uptime = run("uptime -p").stdout.strip().removeprefix("up ")
    host = run("hostname").stdout.strip()

    chosen = rofi_menu(host, f"Uptime: {uptime}", [suspend, logout, reboot, shutdown])
    if not chosen:
        sys.exit(0)

    match chosen:
        case _ if chosen == shutdown:
            run_cmd("--shutdown")
        case _ if chosen == reboot:
            run_cmd("--reboot")
        case _ if chosen == lock:
            if os.path.exists("/usr/bin/betterlockscreen"):
                subprocess.run(shlex.split("betterlockscreen -l"))
            elif os.path.exists("/usr/bin/i3lock"):
                subprocess.run(shlex.split("i3lock"))
        case _ if chosen == suspend:
            run_cmd("--suspend")
        case _ if chosen == logout:
            run_cmd("--logout")


if __name__ == "__main__":
    main()
