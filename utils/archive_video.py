#!/usr/bin/env python3
import subprocess
import argparse
import sys
from pathlib import Path

DEFAULT_CRF = 18
DEFAULT_THREADS = 12
DEFAULT_HEIGHT = None

# (package, description) tuples used by --deps
DEPS = [
    ("ffmpeg", "Provides the `ffmpeg` CLI and the native AAC audio encoder used by this "
               "script. Its libavcodec depends on libx264, so the H.264 encoder comes with it."),
    ("libx264-dev", "Pulls in the libx264 H.264 encoder runtime library. Usually already "
                    "installed as a dependency of ffmpeg; add this if `ffmpeg` was a "
                    "stripped/static build missing libx264."),
]


def archive_video(src: Path, dest: Path, crf: int, threads: int, height: int | None):
    """Re-encode video to H.264 MKV with archival settings."""
    cmd = [
        "ffmpeg", "-hide_banner",
        "-i", str(src),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "slow",
        "-tune", "film",
        "-threads", str(threads),
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
    ]
    if height:
        cmd += ["-vf", f"scale=-2:{height}"]
    cmd += [
        "-c:a", "aac",
        "-b:a", "320k",
        "-map", "0",
        "-y", str(dest),
    ]
    print(f"Running: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Archive video to H.264 MKV",
        epilog="Depends on: ffmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", nargs="?", help="Source video file")
    parser.add_argument("dest", nargs="?", help="Destination MKV file")
    parser.add_argument("-c", "--crf", type=int, default=DEFAULT_CRF,
                        help=f"CRF quality (default: {DEFAULT_CRF})")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS,
                        help=f"CPU threads (default: {DEFAULT_THREADS})")
    parser.add_argument("-s", "--height", type=int, default=DEFAULT_HEIGHT,
                        help="Scale to this height (e.g. 1080), keeps aspect ratio, keeps original fps")
    parser.add_argument("-d", "--deps", action="store_true",
                        help="List dependencies and the apt command to install them, then exit.")
    args = parser.parse_args()

    if args.deps:
        print("Dependencies:")
        for pkg, desc in DEPS:
            print(f"  - {pkg}: {desc}")
        print("\nInstall (Debian/Ubuntu):")
        print(f"  sudo apt install -y {' '.join(pkg for pkg, _ in DEPS)}")
        sys.exit(0)

    if not (args.src and args.dest):
        parser.error("src and dest are required")

    src = Path(args.src).resolve()
    if not src.is_file():
        print(f"Error: file not found: {src}", file=sys.stderr)
        sys.exit(1)

    dest = Path(args.dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    src_size = src.stat().st_size
    print(f"Input:  {src} ({src_size / 1073741824:.1f}GB)")
    print(f"Output: {dest}")
    print(f"CRF: {args.crf}, Threads: {args.threads}", end="")
    if args.height:
        print(f", Scale: {args.height}p", end="")
    print("\n")

    archive_video(src, dest, args.crf, args.threads, args.height)

    dest_size = dest.stat().st_size
    saved = src_size - dest_size
    print(f"\nDone. {src_size / 1073741824:.1f}GB -> {dest_size / 1073741824:.1f}GB "
          f"({saved / 1073741824:.1f}GB saved, {saved / src_size * 100:.0f}%)")


if __name__ == "__main__":
    main()
