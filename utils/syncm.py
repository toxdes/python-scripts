#!/usr/bin/env python3
"""syncm - sync a dir between devices (not for general use, highly specific to my needs)"""

import os
import subprocess
import sys
import shlex
import argparse
import re
import stat
import signal
import threading
import time
import json
import shutil
import tempfile
from dataclasses import dataclass

# constants
# Optional private setting; older injected vars can omit it to disable imports.
IMPORT_DIR = ""
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
AUDIO_EXTENSIONS = {".m4a", ".mp3", ".flac", ".aac", ".ogg", ".opus"}
IMPORT_TEMP_PREFIX = ".syncm-import-"

# base rsync flags shared by every transfer
# --secluded-args keeps spaces in the remote path from being split by the remote shell
RSYNC_BASE = [
    "rsync", "-rlv", "--secluded-args",
    "--no-owner", "--no-group", "--no-perms", "--no-times",
    "--info=progress2", f"--exclude=/{PI_SENTINEL}",
]


def permission_only_failure(stderr: bytes) -> int:
    """Return the count of harmless chmod warnings, or 0 for any other failure."""
    diagnostics = []
    for line in stderr.decode(errors="replace").replace("\r", "\n").splitlines():
        if "rsync:" in line:
            diagnostics.append(line[line.index("rsync:"):].strip())

    permission_warning = re.compile(
        r'rsync: \[(?:generator|receiver)\] failed to set permissions on .+: '
        r'Operation not permitted \(1\)'
    )
    summary = re.compile(
        r'rsync error: some files/attrs were not transferred \(see previous errors\) '
        r'\(code 23\) at .+'
    )
    warnings = sum(bool(permission_warning.fullmatch(line)) for line in diagnostics)
    if warnings and all(
        permission_warning.fullmatch(line) or summary.fullmatch(line)
        for line in diagnostics
    ):
        return warnings
    return 0


def run(
    cmd: list[str],
    dry_run: bool,
    stdin: bytes | None = None,
    tolerate_permission_errors: bool = False,
) -> bool:
    """Print and run a command, returning False on non-zero exit."""
    if dry_run and cmd[0] == "rsync":
        cmd = [cmd[0], "--dry-run", *cmd[1:]]
    print(f"\n>> {shlex.join(cmd)}", file=sys.stderr)
    if dry_run:
        if cmd[0] != "rsync":
            return True
    if tolerate_permission_errors and cmd[0] == "rsync":
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin is not None else None,
            stderr=subprocess.PIPE,
        )
        stderr_chunks = []

        def forward_stderr():
            while chunk := process.stderr.read1(4096):
                stderr_chunks.append(chunk)
                sys.stderr.buffer.write(chunk)
                sys.stderr.buffer.flush()

        reader = threading.Thread(target=forward_stderr)
        reader.start()
        try:
            if stdin is not None:
                try:
                    process.stdin.write(stdin)
                except BrokenPipeError:
                    pass
                finally:
                    try:
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
            returncode = process.wait()
        except KeyboardInterrupt:
            process.send_signal(signal.SIGINT)
            process.wait()
            raise
        finally:
            reader.join()

        if returncode != 0:
            ignored = permission_only_failure(b"".join(stderr_chunks))
            if returncode == 23 and ignored:
                print(
                    f"   ! ignored {ignored} destination permission warning(s); "
                    "file data transferred, destination modes are mount-controlled",
                    file=sys.stderr,
                )
                return True
            print(f"   x exited {returncode}", file=sys.stderr)
            return False
    else:
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
                and not name.startswith(IMPORT_TEMP_PREFIX)
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


def path_component(value: str) -> str:
    """Replace filesystem-unsafe characters while preserving readable names."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(".")
    if not value:
        raise ValueError("empty filename component")
    return value


def tag_number(value: str) -> tuple[int, int]:
    """Read a positive number, optionally followed by /total."""
    number, _, total = value.partition("/")
    result = int(number), int(total or "0")
    if result[0] < 1 or result[1] < 0:
        raise ValueError(f"invalid track/disc number: {value!r}")
    return result


def read_import_tags(path: str) -> dict[str, str]:
    """Probe audio without altering the original file or its embedded metadata."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format_tags:stream=codec_type:stream_tags", "-of", "json", path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise ValueError(f"could not read audio metadata: {result.stderr.strip()}")
    metadata = json.loads(result.stdout)
    audio = [stream for stream in metadata.get("streams", [])
             if stream.get("codec_type") == "audio"]
    if not audio:
        raise ValueError("no audio stream")
    tags = {}
    for source in [*audio, metadata.get("format", {})]:
        tags.update({key.lower(): str(value) for key, value in source.get("tags", {}).items()})
    return tags


def stage_import(snapshot: FileSnapshot, destination: str) -> bool:
    """Publish a complete copy without replacing an existing inbox file."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    temporary = None
    try:
        with open(snapshot.path, "rb") as source, tempfile.NamedTemporaryFile(
            dir=os.path.dirname(destination), prefix=IMPORT_TEMP_PREFIX, delete=False,
        ) as target:
            temporary = target.name
            source_stat = os.fstat(source.fileno())
            if (source_stat.st_dev, source_stat.st_ino, source_stat.st_size, source_stat.st_mtime_ns) != (
                snapshot.device, snapshot.inode, snapshot.size, snapshot.mtime_ns,
            ):
                raise ValueError("source changed before copying")
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        if not unchanged(snapshot) or os.path.getsize(temporary) != snapshot.size:
            raise ValueError("source changed while copying")
        # A settled source can join this run's upload immediately.
        os.utime(temporary, ns=(snapshot.mtime_ns, snapshot.mtime_ns))
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return False
        return True
    finally:
        if temporary is not None:
            os.unlink(temporary)


def import_music(dry_run: bool, settle_seconds: int) -> bool:
    """Copy configured audio into the inbox using metadata-based library paths.

    Originals and non-audio files stay in the source directory. Run after the
    downloader finishes: the age check cannot identify a stalled download.
    """
    if not IMPORT_DIR:
        return True
    directory = os.path.expanduser(IMPORT_DIR)
    if not os.path.isdir(directory):
        print(f"   x import directory does not exist: {directory}", file=sys.stderr)
        return False
    candidates = [snapshot for snapshot in settled_incoming_files(directory, settle_seconds)
                  if os.path.splitext(snapshot.path)[1].lower() in AUDIO_EXTENSIONS]
    if not candidates:
        return True
    if not shutil.which("ffprobe"):
        print("   x audio import requires ffprobe (FFmpeg)", file=sys.stderr)
        return False

    tracks = []
    album_discs = {}
    success = True
    for snapshot in sorted(candidates, key=lambda item: item.relative_path):
        try:
            tags = read_import_tags(snapshot.path)
            compilation = tags.get("compilation", "").lower() in {"1", "true", "yes"}
            artist = "Compilations" if compilation else path_component(tags["album_artist"])
            album = os.path.join(artist, path_component(tags["album"]))
            title = path_component(tags["title"])
            track, _ = tag_number(tags["track"])
            disc, total = tag_number(tags.get("disc", "1"))
            total = max(total, int(tags.get("disctotal", tags.get("totaldiscs", tags.get("disc_total", "0")))))
            album_discs[album] = max(album_discs.get(album, 1), disc, total)
            tracks.append((snapshot, album, title, track, disc))
        except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            print(f"   x cannot import {snapshot.relative_path!r}: {error}", file=sys.stderr)
            success = False

    # Existing references can identify a multi-disc album when totals are absent.
    for album in album_discs:
        for root in (LAPTOP_DIR, incoming_dir()):
            folder = os.path.join(root, album)
            if os.path.isdir(folder):
                with os.scandir(folder) as entries:
                    if any(re.match(r"\d+-\d+ ", entry.name) for entry in entries):
                        album_discs[album] = max(album_discs[album], 2)

    planned = set()
    for snapshot, album, title, track, disc in tracks:
        prefix = f"{disc}-" if album_discs[album] > 1 else ""
        extension = os.path.splitext(snapshot.path)[1].lower()
        relative = os.path.join(album, f"{prefix}{track:02d} {title}{extension}")
        destination = os.path.join(incoming_dir(), relative)
        reference = os.path.join(LAPTOP_DIR, relative)
        if relative in planned or os.path.lexists(destination) or os.path.lexists(reference):
            print(f"   = already present: {relative}", file=sys.stderr)
            continue
        planned.add(relative)
        try:
            if not unchanged(snapshot):
                raise ValueError("source changed while reading metadata")
            if dry_run:
                print(f"   + would import: {snapshot.relative_path} -> {relative}", file=sys.stderr)
            elif stage_import(snapshot, destination):
                print(f"   + imported: {relative}", file=sys.stderr)
        except (OSError, ValueError) as error:
            print(f"   x cannot import {snapshot.relative_path!r}: {error}", file=sys.stderr)
            success = False
    if dry_run and planned:
        print("   ! proposed imports are not staged or included in this rsync dry-run", file=sys.stderr)
    return success


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


def build_skeleton(dry_run: bool) -> int:
    """Create missing empty laptop references from the Pi's regular-file list."""
    if not check_pi_sentinel():
        print(f"   x Pi sentinel missing: {PI_SENTINEL}", file=sys.stderr)
        return 1
    # NUL delimiters preserve spaces, Unicode, and newlines in filenames.
    command = [
        "ssh", f"{PI_USER}@{PI_HOST}",
        f"cd -- {shlex.quote(PI_DIR)} && test -f {shlex.quote(PI_SENTINEL)} "
        "&& find . -type f -print0",
    ]
    print(f"\n>> {shlex.join(command)}", file=sys.stderr)
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE)
    except OSError as error:
        print(f"   x could not list Pi files: {error}", file=sys.stderr)
        return 1
    if result.returncode:
        print(f"   x Pi file listing exited {result.returncode}", file=sys.stderr)
        return 1
    if result.stdout and not result.stdout.endswith(b"\0"):
        print("   x incomplete Pi file listing", file=sys.stderr)
        return 1

    root = os.path.realpath(os.path.expanduser(LAPTOP_DIR))
    paths = []
    # Validate the entire listing before creating any local paths.
    for entry in result.stdout.split(b"\0")[:-1]:
        relative = os.fsdecode(entry[2:]) if entry.startswith(b"./") else ""
        if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
            print(f"   x invalid Pi file path: {entry!r}", file=sys.stderr)
            return 1
        if relative == PI_SENTINEL:
            continue
        destination = os.path.join(root, relative)
        # Preserve existing files, including links, without following them.
        if not os.path.lexists(destination):
            parent = os.path.realpath(os.path.dirname(destination))
            if os.path.commonpath([root, parent]) != root:
                print(f"   x reference parent escapes laptop root: {relative!r}", file=sys.stderr)
                return 1
        paths.append(relative)

    created = existing = 0
    for relative in dict.fromkeys(paths):
        if os.path.lexists(os.path.join(root, relative)):
            existing += 1
            continue
        if dry_run:
            print(f"   + would create reference: {relative!r}", file=sys.stderr)
        elif not create_reference(root, relative):
            return 1
        created += 1
    action = "would create" if dry_run else "created"
    print(f"\nSkeleton: {action} {created} reference(s), kept {existing} existing path(s)", file=sys.stderr)
    return 0


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
    if not import_music(dry_run, settle_seconds):
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
        if not run(
            upload_cmd,
            dry_run,
            stdin=files_from(snapshots),
            tolerate_permission_errors=True,
        ):
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
                        help="Preview imports and rsync changes without modifying either device")
    maintenance = parser.add_mutually_exclusive_group()
    maintenance.add_argument("--init-pi-sentinel", action="store_true",
                             help="Create the Pi safety sentinel after verifying its music mount")
    maintenance.add_argument("--build-skeleton", action="store_true",
                             help="Create missing empty laptop references from the Pi without downloading audio")
    parser.add_argument("--settle-seconds", type=int, default=DEFAULT_SETTLE_SECONDS,
                        help=f"Only upload inbox files unchanged for this long (default: {DEFAULT_SETTLE_SECONDS})")
    parser.add_argument("--max-deletions", type=int, default=DEFAULT_MAX_DELETIONS,
                        help=f"Refuse a sync deleting more than this many paths (default: {DEFAULT_MAX_DELETIONS})")
    parser.add_argument("--verify-contents", action="store_true",
                        help="On Android, checksum every file instead of using the fast size-only check")
    args = parser.parse_args()

    if args.settle_seconds < 0 or args.max_deletions < 0:
        parser.error("--settle-seconds and --max-deletions must be non-negative")
    if args.build_skeleton:
        if args.device != "laptop":
            parser.error("--build-skeleton is only available for laptop")
        return build_skeleton(args.dry_run)
    if args.init_pi_sentinel:
        return 0 if initialize_pi_sentinel() else 1
    if args.device == "laptop":
        return sync_laptop(args.dry_run, args.settle_seconds, args.max_deletions)
    return sync_android(args.dry_run, args.max_deletions, args.verify_contents)


if __name__ == "__main__":
    sys.exit(main())
