#!/usr/bin/env python3
"""syncm - sync a dir between devices (not for general use, highly specific to my needs)"""

import os
import subprocess
import sys
import shlex
import argparse

# constants
# BEGIN SYNCM_VARS -- values injected from syncm_vars.py by install_syncm.sh
LAPTOP_DIR = ""
PI_DIR = ""
ANDROID_DIR = ""

PI_USER = ""
PI_HOST = ""
# END SYNCM_VARS

# base rsync flags shared by every transfer
# --secluded-args keeps spaces in the remote path from being split by the remote shell
RSYNC_BASE = [
    "rsync", "-rlv", "--secluded-args",
    "--no-owner", "--no-group", "--no-perms", "--no-times",
    "--info=progress2", "--prune-empty-dirs",
]


def run(cmd: list[str], dry_run: bool) -> bool:
    """Print and run a command, returning False on non-zero exit."""
    print(f"\n>> {shlex.join(cmd)}", file=sys.stderr)
    if dry_run:
        return True
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"   x exited {res.returncode}", file=sys.stderr)
        return False
    return True


def sync_laptop(dry_run: bool) -> int:
    """Push new files to Pi, hollow local files, pull deletions from Pi."""
    pi_uri = f"{PI_USER}@{PI_HOST}:{PI_DIR}/"
    local = LAPTOP_DIR + "/"

    # push new files from laptop to Pi
    if not run([*RSYNC_BASE, "--ignore-existing", local, pi_uri], dry_run):
        return 1

    # truncate every file on laptop to reclaim space
    find_cmd = ["find", LAPTOP_DIR, "-type", "f", "-exec", "truncate", "-s", "0", "{}", "+"]
    run(find_cmd, dry_run)

    # pull deletions from Pi only, never create new files on laptop
    if not run([*RSYNC_BASE, "--delete", "--ignore-existing", "--existing", pi_uri, local], dry_run):
        return 1

    print("\nLaptop sync complete", file=sys.stderr)
    return 0


def sync_android(dry_run: bool) -> int:
    """Pull from Pi to Android. Pi is the source of truth."""
    pi_uri = f"{PI_USER}@{PI_HOST}:{PI_DIR}/"
    # android sync runs on the device itself, so ~ is the local (android) home
    android = os.path.expanduser(ANDROID_DIR) + "/"

    if not run([*RSYNC_BASE, "--delete", "--ignore-existing", pi_uri, android], dry_run):
        return 1

    print("\nAndroid sync complete", file=sys.stderr)
    return 0


def main():
    # fail early if the private vars were never injected by install_syncm.sh
    if not all([LAPTOP_DIR, PI_DIR, ANDROID_DIR, PI_USER, PI_HOST]):
        print("Error: config not set. Run install_syncm.sh to inject syncm_vars.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Sync Apple Music across devices.")
    parser.add_argument("device", nargs="?", default="laptop", choices=["laptop", "android"],
                        help="Which device to run the sync from (default: laptop)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without executing")
    args = parser.parse_args()

    if args.device == "laptop":
        return sync_laptop(args.dry_run)
    return sync_android(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
