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
    pid = run("pgrep wlsunset").stdout
    if len(pid) > 1:
        run(f"kill -9 {pid}")
    else:
        print("nothing to do")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "kill":
        kill()
    else:
        ps = run("pgrep wlsunset")
        if len(ps.stdout) > 0:
            print("wlsunset is already running")
            return
        wl = run_bg("wlsunset -l 28 -L 77 -t 4000 -T 5000")  # somewhere near delhi
        print(f"wlsunset started\n{wl.stdout}")


if __name__ == "__main__":
    main()
