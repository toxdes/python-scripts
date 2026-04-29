#!/usr/bin/env python3
import shlex
import subprocess
import sys

###
# Usage:
#   1. ./wlsunset.py
#       start wlsunset if not already running
#   2. ./wlsunset.py kill
#       kill wlsunset if already running


def run_bg(cmd):
    print(f"$ {cmd} &")
    return subprocess.Popen(shlex.split(cmd))


def run(cmd):
    print(f"$ {cmd}")
    return subprocess.run(shlex.split(cmd), capture_output=True, text=True)


def kill():
    print("killing wlsunset")
    pid = run("pgrep wlsunset").stdout.strip()
    if pid:
        run(f"kill -9 {pid}")
        subprocess.run(["notify-send", "wlsunset.py", f"wlsunset killed (PID {pid})"])
    else:
        print("nothing to do")
        subprocess.run(["notify-send", "wlsunset.py", "wlsunset is not currently running"])


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "kill":
        kill()
    else:
        ps = run("pgrep wlsunset")
        if ps.stdout.strip():
            print("wlsunset is already running")
            subprocess.run(["notify-send", "wlsunset.py", f"wlsunset is already running (PID {ps.stdout.strip()})"])
            return
        wl = run_bg("wlsunset -l 28 -L 77 -t 4000 -T 5000")  # somewhere near delhi
        print(f"wlsunset started\n{wl.stdout}")
        subprocess.run(["notify-send", "wlsunset.py", "wlsunset started (lat 28, lon 77, ~Delhi)"])


if __name__ == "__main__":
    main()
