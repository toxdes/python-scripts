#!/usr/bin/env python3
"""syncm - sync a dir between devices (not for general use, highly specific to my needs)"""

import os
import subprocess
import sys
import shlex
import argparse
import stat
import time
from dataclasses import dataclass

# constants
# BEGIN SYNCM_VARS -- values injected from syncm_vars.py by the syncm installer
LAPTOP_DIR = ""
PI_DIR = ""
ANDROID_DIR = ""

PI_USER = ""
PI_HOST = ""
# END SYNCM_VARS

PI_SENTINEL = ".syncm-pi-root"
DEFAULT_SETTLE_SECONDS = 120
DEFAULT_MAX_DELETIONS = 100

# base rsync flags shared by every transfer
# --secluded-args keeps spaces in the remote path from being split by the remote shell
RSYNC_BASE = [
    "rsync", "-rlv", "--secluded-args",
    "--no-owner", "--no-group", "--no-perms", "--no-times",
    "--info=progress2", f"--exclude=/{PI_SENTINEL}",
]


def run(cmd: list[str], dry_run: bool, stdin: bytes | None = None) -> bool:
    """Print and run a command, returning False on non-zero exit."""
    if dry_run and cmd[0] == "rsync":
        cmd = [cmd[0], "--dry-run", *cmd[1:]]
    print(f"\n>> {shlex.join(cmd)}", file=sys.stderr)
    if dry_run:
        if cmd[0] != "rsync":
            return True
    res = subprocess.run(cmd, input=stdin)
    if res.returncode != 0:
        print(f"   x exited {res.returncode}", file=sys.stderr)
        return False
    return True


@dataclass(frozen=True)
class FileSnapshot:
    """A settled incoming file and the metadata used to avoid truncating it."""

    path: str
    relative_path: str
    device: int
    inode: int
    size: int
    mtime_ns: int


def incoming_dir() -> str:
    """Return the dedicated, sibling download inbox for the laptop."""
    root = os.path.dirname(os.path.normpath(LAPTOP_DIR))
    name = os.path.basename(os.path.normpath(LAPTOP_DIR))
    return os.path.join(root, f"{name}.incoming")


def settled_incoming_files(directory: str, settle_seconds: int) -> list[FileSnapshot]:
    """List stable non-empty regular files from the dedicated download inbox.

    A downloader should write a temporary file and atomically rename it when
    complete.  The age check is a second guard against uploading an active
    download or removing it while it is still being written.
    """
    cutoff = time.time_ns() - settle_seconds * 1_000_000_000
    files: list[FileSnapshot] = []
    for root, _, names in os.walk(directory):
        for name in names:
            path = os.path.join(root, name)
            try:
                file_stat = os.lstat(path)
            except FileNotFoundError:
                # A downloader may finish or remove a file while we scan.
                continue
            if (
                stat.S_ISREG(file_stat.st_mode)
                and file_stat.st_size > 0
                and file_stat.st_mtime_ns <= cutoff
                and os.path.relpath(path, directory) != PI_SENTINEL
            ):
                relative_path = os.path.relpath(path, directory)
                files.append(FileSnapshot(
                    path=path,
                    relative_path=relative_path,
                    device=file_stat.st_dev,
                    inode=file_stat.st_ino,
                    size=file_stat.st_size,
                    mtime_ns=file_stat.st_mtime_ns,
                ))
    return files


def files_from(snapshots: list[FileSnapshot]) -> bytes:
    """Create the NUL-delimited rsync --files-from input."""
    paths = [os.fsencode(snapshot.relative_path) for snapshot in snapshots]
    return b"\0".join(paths) + (b"\0" if paths else b"")


def unchanged(snapshot: FileSnapshot) -> bool:
    """Return whether an inbox file stayed untouched during rsync."""
    try:
        file_stat = os.lstat(snapshot.path)
    except FileNotFoundError:
        return False
    return (
        stat.S_ISREG(file_stat.st_mode)
        and file_stat.st_dev == snapshot.device
        and file_stat.st_ino == snapshot.inode
        and file_stat.st_size == snapshot.size
        and file_stat.st_mtime_ns == snapshot.mtime_ns
    )


def create_reference(reference_root: str, relative_path: str) -> bool:
    """Create an empty reference without modifying any existing local file."""
    reference_path = os.path.join(reference_root, relative_path)
    try:
        os.makedirs(os.path.dirname(reference_path), exist_ok=True)
        fd = os.open(reference_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return True
    except OSError as error:
        print(f"   x could not create reference {reference_path!r}: {error}", file=sys.stderr)
        return False
    else:
        os.close(fd)
        return True


def remove_uploaded_incoming(snapshots: list[FileSnapshot], reference_root: str) -> bool:
    """Replace uploaded inbox files with references only after a safe upload."""
    success = True
    for snapshot in snapshots:
        if not unchanged(snapshot):
            print(f"   ! kept changed inbox file: {snapshot.relative_path}", file=sys.stderr)
            success = False
            continue
        if not create_reference(reference_root, snapshot.relative_path):
            success = False
            continue
        try:
            os.unlink(snapshot.path)
        except OSError as error:
            print(f"   x could not remove uploaded file {snapshot.path!r}: {error}", file=sys.stderr)
            success = False
    return success


def check_pi_sentinel() -> bool:
    """Refuse destructive sync work unless the expected Pi music root is mounted."""
    sentinel = f"{PI_DIR.rstrip('/')}/{PI_SENTINEL}"
    remote_command = f"test -f {shlex.quote(sentinel)}"
    return run(["ssh", f"{PI_USER}@{PI_HOST}", remote_command], dry_run=False)


def initialize_pi_sentinel() -> bool:
    """Create the sentinel once, after the Pi music mount has been verified."""
    sentinel = f"{PI_DIR.rstrip('/')}/{PI_SENTINEL}"
    remote_command = f"test -e {shlex.quote(sentinel)} || (umask 077 && : > {shlex.quote(sentinel)})"
    return run(["ssh", f"{PI_USER}@{PI_HOST}", remote_command], dry_run=False)


def planned_deletions(sync_cmd: list[str]) -> list[str] | None:
    """Return destination paths rsync would delete, without changing either side."""
    preview_cmd = [sync_cmd[0], "--dry-run", "--out-format=%i|%n", *sync_cmd[1:]]
    print(f"\n>> {shlex.join(preview_cmd)}", file=sys.stderr)
    res = subprocess.run(preview_cmd, text=True, stdout=subprocess.PIPE)
    if res.returncode != 0:
        print(f"   x exited {res.returncode}", file=sys.stderr)
        return None
    return [
        line.partition("|")[2]
        for line in res.stdout.splitlines()
        if line.startswith("*deleting")
    ]


def deletion_is_safe(sync_cmd: list[str], max_deletions: int) -> bool:
    """Require explicit opt-in before an unexpectedly large deletion batch."""
    deletions = planned_deletions(sync_cmd)
    if deletions is None:
        return False
    if len(deletions) <= max_deletions:
        return True
    print(
        f"   x refusing to delete {len(deletions)} paths (limit: {max_deletions}). "
        "Check the Pi mount, then rerun with --max-deletions.",
        file=sys.stderr,
    )
    for path in deletions[:10]:
        print(f"     would delete: {path}", file=sys.stderr)
    return False


def sync_laptop(dry_run: bool, settle_seconds: int, max_deletions: int) -> int:
    """Upload settled inbox files, then remove laptop references absent on Pi."""
    pi_uri = f"{PI_USER}@{PI_HOST}:{PI_DIR}/"
    references = LAPTOP_DIR + "/"
    inbox = incoming_dir()

    if not check_pi_sentinel():
        print(f"   x Pi sentinel missing: {PI_SENTINEL}", file=sys.stderr)
        return 1
    if os.path.isdir(inbox):
        snapshots = settled_incoming_files(inbox, settle_seconds)
    elif dry_run:
        print(f"\n>> inbox does not exist yet: {inbox}", file=sys.stderr)
        snapshots = []
    else:
        os.makedirs(inbox, exist_ok=True)
        snapshots = []

    if snapshots:
        upload_cmd = [
            *RSYNC_BASE, "--ignore-existing", "--from0", "--files-from=-", inbox + "/", pi_uri,
        ]
        if not run(upload_cmd, dry_run, stdin=files_from(snapshots)):
            return 1
    if not dry_run and not remove_uploaded_incoming(snapshots, LAPTOP_DIR):
        return 1

    # Pull deletions from Pi only; do not create or change laptop references.
    delete_cmd = [*RSYNC_BASE, "--delete", "--ignore-existing", "--existing", pi_uri, references]
    if not deletion_is_safe(delete_cmd, max_deletions):
        return 1
    if not run(delete_cmd, dry_run):
        return 1

    print("\nLaptop sync complete", file=sys.stderr)
    return 0


def sync_android(dry_run: bool, max_deletions: int, verify_contents: bool) -> int:
    """Pull from Pi to Android. Pi is the source of truth."""
    pi_uri = f"{PI_USER}@{PI_HOST}:{PI_DIR}/"
    # android sync runs on the device itself, so ~ is the local (android) home
    android = os.path.expanduser(ANDROID_DIR) + "/"

    if not check_pi_sentinel():
        print(f"   x Pi sentinel missing: {PI_SENTINEL}", file=sys.stderr)
        return 1
    # Size checks catch missing/truncated files without hashing the whole Pi
    # library on every run.  Use --verify-contents for an occasional full audit.
    comparison_flag = "--checksum" if verify_contents else "--size-only"
    delete_cmd = [*RSYNC_BASE, comparison_flag, "--delete", pi_uri, android]
    if not deletion_is_safe(delete_cmd, max_deletions):
        return 1
    if not run(delete_cmd, dry_run):
        return 1

    print("\nAndroid sync complete", file=sys.stderr)
    return 0


def main():
    # fail early if the private vars were never injected by the syncm installer
    if not all([LAPTOP_DIR, PI_DIR, ANDROID_DIR, PI_USER, PI_HOST]):
        print("Error: config not set. Run the syncm installer to inject syncm_vars.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Sync Apple Music across devices.")
    parser.add_argument("device", nargs="?", default="laptop", choices=["laptop", "android"],
                        help="Which device to run the sync from (default: laptop)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show rsync changes without modifying either device")
    parser.add_argument("--init-pi-sentinel", action="store_true",
                        help="Create the Pi safety sentinel after verifying its music mount")
    parser.add_argument("--settle-seconds", type=int, default=DEFAULT_SETTLE_SECONDS,
                        help=f"Only upload inbox files unchanged for this long (default: {DEFAULT_SETTLE_SECONDS})")
    parser.add_argument("--max-deletions", type=int, default=DEFAULT_MAX_DELETIONS,
                        help=f"Refuse a sync deleting more than this many paths (default: {DEFAULT_MAX_DELETIONS})")
    parser.add_argument("--verify-contents", action="store_true",
                        help="On Android, checksum every file instead of using the fast size-only check")
    args = parser.parse_args()

    if args.settle_seconds < 0 or args.max_deletions < 0:
        parser.error("--settle-seconds and --max-deletions must be non-negative")
    if args.init_pi_sentinel:
        return 0 if initialize_pi_sentinel() else 1
    if args.device == "laptop":
        return sync_laptop(args.dry_run, args.settle_seconds, args.max_deletions)
    return sync_android(args.dry_run, args.max_deletions, args.verify_contents)


if __name__ == "__main__":
    sys.exit(main())
