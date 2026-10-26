#!/usr/bin/env python3
import subprocess
import argparse
import sys
from pathlib import Path

DEFAULT_CRF = 18
DEFAULT_THREADS = 12
DEFAULT_HEIGHT = None
EXTENSIONS = {
    ".3g2", ".3gp", ".avi", ".m2ts", ".m2v", ".m4v", ".mkv", ".mov",
    ".mp4", ".mpeg", ".mpg", ".mts", ".ogv", ".ts", ".vob", ".webm",
    ".wmv",
}

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


def video_files(paths: list[Path]) -> list[Path]:
    videos = {}
    for path in paths:
        path = path.resolve()
        if not path.exists():
            raise ValueError(f"Input not found: {path}")
        if path.is_dir():
            candidates = path.iterdir()
        elif path.is_file():
            candidates = [path]
        else:
            raise ValueError(f"Input is not a file or directory: {path}")
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in EXTENSIONS:
                videos[candidate.resolve()] = candidate.resolve()
    return sorted(videos.values())


def main():
    parser = argparse.ArgumentParser(
        description="Archive videos to H.264 MKV",
        epilog="Depends on: ffmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Video files or directories containing videos")
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

    if not args.paths:
        parser.error("at least one video file or directory is required")

    try:
        videos = video_files([Path(path) for path in args.paths])
    except ValueError as e:
        parser.error(str(e))

    if not videos:
        parser.error("no supported video files found in the given inputs")

    dest_dir = Path.cwd() / "vid"
    destinations = [dest_dir / f"{src.stem}.mkv" for src in videos]
    if len(set(destinations)) != len(destinations):
        parser.error("multiple input videos would have the same output name in ./vid")
    if any(src == dest.resolve() for src, dest in zip(videos, destinations)):
        parser.error("an input file would be overwritten in ./vid; choose inputs outside the output directory")
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Archiving {len(videos)} videos (CRF={args.crf}) -> {dest_dir}\n")

    total_src = 0
    total_dst = 0
    failed = 0
    width = len(str(len(videos)))

    for i, src in enumerate(videos, 1):
        dest = dest_dir / f"{src.stem}.mkv"
        print(f"[{i:>{width}}/{len(videos)}] {src.name} ... ", flush=True)
        try:
            src_size = src.stat().st_size
            archive_video(src, dest, args.crf, args.threads, args.height)
            dest_size = dest.stat().st_size
            saved = src_size - dest_size
            pct = saved / src_size * 100 if src_size else 0
            print(f"Done. {src_size / 1048576:.1f}MB -> {dest_size / 1048576:.1f}MB ({pct:.0f}% smaller)\n")
            total_src += src_size
            total_dst += dest_size
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"FAILED: {e}\n", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"ERROR: {e}\n", file=sys.stderr)

    if total_src:
        saved = total_src - total_dst
        pct = saved / total_src * 100
        print(f"Total. {total_src / 1048576:.1f}MB -> {total_dst / 1048576:.1f}MB "
              f"({saved / 1048576:.1f}MB saved, {pct:.0f}%)")
    print(f"Files failed: {failed}/{len(videos)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
