#!/usr/bin/env python3
import os
import subprocess
import sys
import socket

DIR = os.path.expanduser("~/.config/rofi/powermenu/type-1")
THEME = "style-1"
THEME_PATH = f"{DIR}/{THEME}.rasi"

shutdown = " Shutdown"
reboot = " Reboot"
lock = " Lock"
suspend = " Suspend"
hibernate = "󰒲 Hibernate"
logout = " Logout"

yes = " Yes"
no = " No"


def run(*cmd):
    return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            )


def rofi_menu(prompt, mesg, options):
    cmd = [
            "rofi",
            "-dmenu",
            "-p", prompt,
            "-mesg", mesg,
            "-theme", THEME_PATH,
            ]

    result = subprocess.run(
            cmd,
            input="\n".join(options),
            capture_output=True,
            text=True,
            )

    return result.stdout.strip()


def confirm_menu():
    cmd = [
            "rofi",
            "-theme-str",
            "window {location: center; anchor: center; fullscreen: false; width: 250px;}",
            "-theme-str",
            'mainbox {children: [ "message", "listview" ];}',
            "-theme-str",
            "listview {columns: 2; lines: 1;}",
            "-theme-str",
            "element-text {horizontal-align: 0.5;}",
            "-theme-str",
            "textbox {horizontal-align: 0.5;}",
            "-dmenu",
            "-p", "Confirmation",
            "-mesg", "Are you Sure?",
            "-theme", THEME_PATH,
            ]

    result = subprocess.run(
            cmd,
            input=f"{yes}\n{no}",
            capture_output=True,
            text=True,
            )

    return result.stdout.strip() == yes


COMMANDS = {
        lock: ["swaylock", "-f", "-c", "000000"],
        suspend: ["systemctl", "suspend"],
        hibernate: ["systemctl", "hibernate"],
        logout: ["swaymsg", "exit"],
        reboot: ["systemctl", "reboot"],
        shutdown: ["systemctl", "poweroff"],
        }


def main():
    uptime = run("uptime", "-p").stdout.strip().removeprefix("up ")
    host = socket.gethostname()

    chosen = rofi_menu(
            host,
            f"Uptime: {uptime}",
            [lock, suspend, hibernate, logout, reboot, shutdown],
            )

    if chosen not in COMMANDS:
        return

    # Lock immediately; confirm other actions.
    if chosen != lock and not confirm_menu():
        return

    result = subprocess.run(COMMANDS[chosen])

    if result.returncode != 0:
        print(f"Failed to execute: {chosen}", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
