#!/usr/bin/env python3
import shlex
import subprocess
import sys
from enum import Enum, auto


# configure these values before usage
class Config(Enum):
    DISPLAY_SERVER = "wayland"
    LAPTOP_DISPLAY = "eDP-1"
    EXTERNAL_DISPLAY = "HDMI-A-1"
    EXTERNAL_DISPLAY_POSITION = "left"


class DisplayMode(Enum):
    laptop_only = auto()
    external_only = auto()
    external_mirrors_laptop = auto()
    external_extends_laptop = auto()


def usage():
    print(f"Usage: {sys.argv[0]} <{' | '.join([mode.name for mode in DisplayMode])}>")


def get_cmds_for_mode(mode):
    laptop = Config.LAPTOP_DISPLAY.value
    external = Config.EXTERNAL_DISPLAY.value
    position = Config.EXTERNAL_DISPLAY_POSITION.value
    display_server = Config.DISPLAY_SERVER.value

    if display_server == "wayland":
        if mode == DisplayMode.laptop_only:
            return [
                f"wlr-randr --output {external} --off",
                f"wlr-randr --output {laptop} --on",
            ]
        elif mode == DisplayMode.external_only:
            return [
                f"wlr-randr --output {laptop} --off",
                f"wlr-randr --output {external} --on",
            ]
        elif mode == DisplayMode.external_mirrors_laptop:
            return [
                f"wlr-randr --output {external} --on",
                f"wlr-randr --output {laptop} --on",
            ]
        elif mode == DisplayMode.external_extends_laptop:
            # wlr-randr doesn't support relative positioning (--left-of, etc.)
            # Use absolute positioning: HDMI at 0,0 and eDP positioned relative to it
            if position == "left":
                pos = "1920,0"
            elif position == "right":
                pos = "-1920,0"
            else:
                pos = "0,0"
            return [
                f"wlr-randr --output {laptop} --off",
                f"wlr-randr --output {external} --off",
                "sleep 1",
                f"wlr-randr --output {external} --on --pos 0,0",
                f"wlr-randr --output {laptop} --on --pos {pos}",
            ]
    else:
        if mode == DisplayMode.laptop_only:
            return [
                f"xrandr --output {external} --off",
                f"xrandr --output {laptop} --auto --primary",
            ]
        elif mode == DisplayMode.external_only:
            return [
                f"xrandr --output {laptop} --off",
                f"xrandr --output {external} --auto --primary",
            ]
        elif mode == DisplayMode.external_mirrors_laptop:
            return [
                f"xrandr --output {external} --auto --same-as {laptop}",
                f"xrandr --output {laptop} --primary",
            ]
        elif mode == DisplayMode.external_extends_laptop:
            return [
                f"xrandr --output {laptop} --off",
                f"xrandr --output {external} --off",
                "sleep 1",
                f"xrandr --output {external} --auto --primary",
                f"xrandr --output {laptop} --auto --{position}-of {external}",
            ]

    return []


if __name__ == "__main__":
    try:
        mode_name = sys.argv[1]
        mode = DisplayMode[mode_name]
        cmds = get_cmds_for_mode(mode)
        for cmd in cmds:
            subprocess.run(shlex.split(cmd), check=True)
    except IndexError:
        usage()
    except KeyError:
        usage()
