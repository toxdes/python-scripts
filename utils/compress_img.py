#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from pathlib import Path

DEFAULT_QUALITY = 85
EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}

# (package, description) tuples used by --deps
DEPS = [
    ("imagemagick", "Provides the `convert` command used to re-encode JPEGs."),
    ("libimage-exiftool-perl", "Provides the `exiftool` command used to copy EXIF metadata."),
]


def compress_image(src: Path, dest: Path, quality: int) -> tuple[int, int]:
    subprocess.run(
        ["convert", str(src), "-quality", str(quality), str(dest)],
        check=True,
        capture_output=True,
    )
    # Copy EXIF metadata (date, camera settings, etc.) from source
    subprocess.run(
        ["exiftool", "-F", "-TagsFromFile", str(src), "-Exif:All", "-overwrite_original", str(dest)],
        check=True,
        capture_output=True,
    )
    return src.stat().st_size, dest.stat().st_size


def main():
    parser = argparse.ArgumentParser(
        description="Compress JPEG images (re-encode, preserving EXIF metadata)",
        epilog="Depends on: ImageMagick (convert), exiftool",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", nargs="?", help="Source directory with JPEG images")
    parser.add_argument("dest", nargs="?", help="Destination directory for compressed images")
    parser.add_argument("-q", "--quality", type=int, default=DEFAULT_QUALITY,
                        help=f"JPEG quality 1-100 (default: {DEFAULT_QUALITY})")
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

    src_dir = Path(args.src).resolve()
    dest_dir = Path(args.dest).resolve()
    quality = args.quality

    if not 1 <= quality <= 100:
        print(f"Error: quality must be 1-100, got {quality}", file=sys.stderr)
        sys.exit(1)

    if not src_dir.is_dir():
        print(f"Error: source directory not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(f for f in src_dir.iterdir() if f.suffix in EXTENSIONS)
    if not images:
        print(f"No JPEG files found in {src_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Compressing {len(images)} images (quality={quality}) -> {dest_dir}\n")

    total_src = 0
    total_dst = 0
    width = len(str(len(images)))

    for i, src in enumerate(images, 1):
        dest = dest_dir / src.name
        print(f"[{i:>{width}}/{len(images)}] {src.name} ... ", end="", flush=True)
        try:
            src_size, dst_size = compress_image(src, dest, quality)
            saved = src_size - dst_size
            pct = saved / src_size * 100
            print(f"{src_size / 1048576:.1f}MB -> {dst_size / 1048576:.1f}MB ({pct:.0f}% smaller)")
            total_src += src_size
            total_dst += dst_size
        except subprocess.CalledProcessError as e:
            print(f"FAILED: {e}")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nDone. {total_src / 1048576:.1f}MB -> {total_dst / 1048576:.1f}MB "
          f"({(total_src - total_dst) / 1048576:.1f}MB saved, {(total_src - total_dst) / total_src * 100:.0f}%)")


if __name__ == "__main__":
    main()
