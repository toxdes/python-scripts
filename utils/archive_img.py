#!/usr/bin/env python3
import sys
import subprocess
import argparse
from pathlib import Path

DEFAULT_QUALITY = 85
EXTENSIONS = {".jpg", ".jpeg"}

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


def image_files(paths: list[Path]) -> list[Path]:
    images = {}
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
                images[candidate.resolve()] = candidate.resolve()
    return sorted(images.values())


def main():
    parser = argparse.ArgumentParser(
        description="Compress JPEG images (re-encode, preserving EXIF metadata)",
        epilog="Depends on: ImageMagick (convert), exiftool",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Image files or directories containing JPEG images")
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

    if not args.paths:
        parser.error("at least one image file or directory is required")

    if not 1 <= args.quality <= 100:
        parser.error(f"quality must be 1-100, got {args.quality}")

    try:
        images = image_files([Path(path) for path in args.paths])
    except ValueError as e:
        parser.error(str(e))

    if not images:
        parser.error("no JPEG files found in the given inputs")

    dest_dir = Path.cwd() / "img"
    destinations = [dest_dir / src.name for src in images]
    if len(set(destinations)) != len(destinations):
        parser.error("multiple input files have the same name; cannot write unique files to ./img")
    if any(src == dest.resolve() for src, dest in zip(images, destinations)):
        parser.error("an input file is already in ./img; choose inputs outside the output directory")
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Compressing {len(images)} images (quality={args.quality}) -> {dest_dir}\n")

    total_src = 0
    total_dst = 0
    failed = 0
    width = len(str(len(images)))

    for i, src in enumerate(images, 1):
        dest = dest_dir / src.name
        print(f"[{i:>{width}}/{len(images)}] {src.name} ... ", end="", flush=True)
        try:
            src_size, dst_size = compress_image(src, dest, args.quality)
            saved = src_size - dst_size
            pct = saved / src_size * 100 if src_size else 0
            print(f"{src_size / 1048576:.1f}MB -> {dst_size / 1048576:.1f}MB ({pct:.0f}% smaller)")
            total_src += src_size
            total_dst += dst_size
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR: {e}")

    if total_src:
        saved = total_src - total_dst
        pct = saved / total_src * 100
        print(f"\nDone. {total_src / 1048576:.1f}MB -> {total_dst / 1048576:.1f}MB "
              f"({saved / 1048576:.1f}MB saved, {pct:.0f}%)")
    print(f"Files failed: {failed}/{len(images)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
