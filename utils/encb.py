#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["boto3"]
# ///

"""Encrypted backup: create a GPG-encrypted tar.gz archive of given paths
and upload to Backblaze B2 and AWS S3.

Usage:
    ./encb.py --env ~/.encb.env /path/to/dir /path/to/file
    ./encb.py --env ~/.encb.env --name mybackup /path/to/dir
    ./encb.py --env ~/.encb.env --test-connectivity
    ./encb.py --env ~/.encb.env --download encb-20260704120000.tar.gz.gpg

Environment (via --env PATH):
    B2_KEY_ID               Backblaze B2 key ID
    B2_APPLICATION_KEY      Backblaze B2 application key
    B2_BUCKET_NAME          Backblaze B2 bucket name
    B2_BUCKET_ENDPOINT      Backblaze B2 bucket endpoint

    AWS_ACCESS_KEY          AWS access key ID
    AWS_SECRET_KEY          AWS secret access key
    AWS_REGION              AWS region
    AWS_BUCKET_NAME         AWS S3 bucket name
    AWS_STORAGE_CLASS       S3 storage class (e.g. STANDARD, GLACIER)
"""

import argparse
import getpass
import io
import logging
import os
import shlex
import stat
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config

log = logging.getLogger("encb")

# ANSI colors
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.INFO: "",
        logging.WARNING: _YELLOW,
        logging.ERROR: _RED,
    }

    def format(self, record):
        msg = record.getMessage()
        color = self.COLORS.get(record.levelno, "")
        if color:
            return f"{color}{msg}{_RESET}"
        return msg


def load_env_file(path):
    env_file = Path(path)
    if not env_file.is_file():
        log.error("%s not found", path)
        sys.exit(1)

    loaded = 0
    with open(env_file) as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                log.warning("%s:%d not a KEY=VALUE line, skipping", path, lineno)
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key not in os.environ:
                os.environ[key] = value.strip()
                loaded += 1
    log.info("Loaded %d variable(s) from %s", loaded, path)


def check_required(*vars_):
    missing = [v for v in vars_ if not os.environ.get(v)]
    if missing:
        log.error("missing required env vars: %s", ", ".join(missing))
        log.error("Provide them via --env PATH or in the environment")
        sys.exit(1)


def make_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def validate_paths(paths):
    for p in paths:
        if not os.path.exists(p):
            log.error("path does not exist: %s", p)
            sys.exit(1)
    return paths


def get_paths_size(paths):
    """Return total regular-file data bytes, matching tar.add() exactly.

    Mirrors tarfile's gettarinfo+add: os.lstat, S_ISREG check,
    (dev,ino) hard-link dedup, sorted(os.listdir()) recursion.
    """
    seen = set()
    total = 0

    def walk(name):
        nonlocal total
        try:
            st = os.lstat(name)
        except OSError:
            return
        m = st.st_mode
        if stat.S_ISREG(m):
            inode = (st.st_dev, st.st_ino)
            if inode not in seen:
                seen.add(inode)
                total += st.st_size
        elif stat.S_ISDIR(m):
            try:
                items = sorted(os.listdir(name))
            except OSError:
                return
            for item in items:
                walk(os.path.join(name, item))

    for p in paths:
        p = os.path.realpath(p)
        if not os.path.lexists(p):
            log.error("path does not exist: %s", p)
            sys.exit(1)
        walk(p)

    return total


def get_available_memory():
    """Return an estimate of available memory, or 0 if unavailable.

    Linux exposes a relatively useful estimate through /proc/meminfo. On
    other Unix-like systems, fall back to the portable sysconf interface.
    Returning 0 is intentional: create_archive() will then use streaming
    mode instead of making an in-memory archive based on an unknown value.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024  # kB to bytes
    except (OSError, ValueError, IndexError):
        pass

    try:
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if available_pages > 0 and page_size > 0:
            return available_pages * page_size
    except (AttributeError, OSError, ValueError):
        pass

    return 0


def _format_size(n):
    for unit in ("", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n //= 1024
    return f"{n}P"


class _ProgressBar:
    def __init__(self, total, desc=""):
        self.total = total
        self.current = 0
        self.desc = desc
        self._start = time.monotonic()
        self._last_draw = 0.0
        self._is_tty = sys.stderr.isatty()

    def update(self, n):
        self.current += n
        if self._is_tty and self.total:
            now = time.monotonic()
            if now - self._last_draw >= 0.016:
                self._last_draw = now
                self._draw()

    def _draw(self):
        pct = min(self.current / self.total, 1.0)
        elapsed = int(time.monotonic() - self._start)
        elapsed_str = f"{elapsed // 60}:{elapsed % 60:02d}"
        cur = _format_size(self.current)
        total = _format_size(self.total)
        filled = int(pct * 30)
        bar = "#" * filled + "-" * (30 - filled)
        print(f"\r{self.desc}: [{bar}] {pct:.0%} {_GREEN}{cur}/{total}{_RESET} [{elapsed_str}]",
              end="", file=sys.stderr, flush=True)

    def close(self):
        if self._is_tty and self.current:
            self._draw()
            print(file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _patch_addfile(tar, pbar):
    """Monkey-patch tar.addfile to count file data bytes (not headers/padding)."""
    original = tar.addfile
    def tracking_addfile(tarinfo, fileobj=None):
        if fileobj is not None and tarinfo.isfile() and tarinfo.size:
            pbar.update(tarinfo.size)
        return original(tarinfo, fileobj)
    tar.addfile = tracking_addfile


def _gpg_cmd(output):
    return ["gpg", "--batch", "--symmetric", "--cipher-algo", "AES256",
            "--s2k-cipher-algo", "AES256",
            "--s2k-digest-algo", "SHA512",
            "--s2k-count", "65011712",
            "--compress-algo", "none",
            "--output", str(output)]


def read_passphrase():
    pw = getpass.getpass("Enter encryption passphrase: ")
    if not pw:
        log.error("passphrase cannot be empty")
        sys.exit(1)
    if "\n" in pw:
        log.error("passphrase must not contain newlines")
        sys.exit(1)
    confirm = getpass.getpass("Confirm passphrase: ")
    if pw != confirm:
        log.error("passphrases do not match")
        sys.exit(1)
    return pw


def create_archive(paths, ts, passphrase, name=None):
    if name:
        prefix = f"encb-{name}-{ts}"
    else:
        prefix = f"encb-{ts}"
    gpg_name = f"{prefix}.tar.gz.gpg"
    final_path = Path.cwd() / gpg_name

    total_size = get_paths_size(paths)
    avail_mem = get_available_memory()

    if avail_mem and total_size < avail_mem * 0.5:
        return _create_archive_mem(paths, prefix, final_path, total_size, passphrase)
    else:
        return _create_archive_stream(paths, prefix, final_path, total_size, passphrase)


def _create_archive_mem(paths, prefix, final_path, total_size, passphrase):
    log.info("Building tar.gz in memory (%s input)...", _format_size(total_size))
    tar_buf = io.BytesIO()
    with _ProgressBar(total=total_size, desc="tar.gz") as pbar:
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
            _patch_addfile(tar, pbar)
            for p in paths:
                src = Path(p).resolve()
                tar.add(str(src), arcname=f"{prefix}/{src.name}")

    tar_data = tar_buf.getvalue()
    log.info("tar.gz size: %s", _format_size(len(tar_data)))

    log.info(f"{_CYAN + _BOLD}[+] gpg --symmetric ... -o {final_path}{_RESET}")
    subprocess.run(
        _gpg_cmd(final_path) + ["--passphrase-fd", "0"],
        input=passphrase.encode() + b"\n" + tar_data,
        check=True,
    )

    log.info(f"Archive created: {_GREEN}{final_path}{_RESET}")
    return final_path


def _create_archive_stream(paths, prefix, final_path, total_size, passphrase):
    log.info("Building tar.gz via pipe (%s input, streaming)...", _format_size(total_size))

    gpg_cmd = _gpg_cmd(final_path) + ["--passphrase-fd", "0"]
    gpg_cmd_str = " ".join(shlex.quote(str(c)) for c in gpg_cmd)
    log.info(f"{_CYAN + _BOLD}[+] {gpg_cmd_str}{_RESET}")

    gpg = subprocess.Popen(gpg_cmd, stdin=subprocess.PIPE)
    try:
        gpg.stdin.write(passphrase.encode() + b"\n")
        gpg.stdin.flush()
        with _ProgressBar(total=total_size, desc="tar.gz") as pbar:
            with tarfile.open(fileobj=gpg.stdin, mode="w:gz") as tar:
                _patch_addfile(tar, pbar)
                for p in paths:
                    src = Path(p).resolve()
                    tar.add(str(src), arcname=f"{prefix}/{src.name}")
    finally:
        gpg.stdin.close()
        gpg.wait()
        if gpg.returncode != 0:
            raise subprocess.CalledProcessError(gpg.returncode, gpg_cmd)

    log.info(f"Archive created: {_GREEN}{final_path}{_RESET}")
    return final_path


def make_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["AWS_SECRET_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def make_b2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["B2_BUCKET_ENDPOINT"],
        aws_access_key_id=os.environ["B2_KEY_ID"],
        aws_secret_access_key=os.environ["B2_APPLICATION_KEY"],
        config=Config(signature_version="s3v4"),
    )


def upload_to_s3(archive_path):
    client = make_s3_client()
    bucket = os.environ["AWS_BUCKET_NAME"]
    storage_class = os.environ.get("AWS_STORAGE_CLASS", "STANDARD")
    file_size = archive_path.stat().st_size

    extra = {}
    if storage_class:
        extra["StorageClass"] = storage_class

    log.info("Uploading to S3 bucket %s (storage class: %s)...",
             bucket, storage_class)
    with _ProgressBar(total=file_size, desc="S3") as pbar:
        client.upload_file(
            str(archive_path),
            bucket,
            archive_path.name,
            ExtraArgs=extra,
            Callback=lambda n: pbar.update(n),
        )
    log.info(f"Uploaded to S3: {_GREEN}s3://{bucket}/{archive_path.name}{_RESET}")


def upload_to_b2(archive_path):
    client = make_b2_client()
    bucket = os.environ["B2_BUCKET_NAME"]
    file_size = archive_path.stat().st_size

    log.info("Uploading to B2 bucket %s...", bucket)
    with _ProgressBar(total=file_size, desc="B2") as pbar:
        client.upload_file(
            str(archive_path),
            bucket,
            archive_path.name,
            Callback=lambda n: pbar.update(n),
        )
    log.info(f"Uploaded to B2: {_GREEN}b2://{bucket}/{archive_path.name}{_RESET}")


def download_from_b2(filename):
    client = make_b2_client()
    bucket = os.environ["B2_BUCKET_NAME"]
    dest = Path.cwd() / filename

    log.info("Downloading from B2: b2://%s/%s", bucket, filename)
    size = client.head_object(Bucket=bucket, Key=filename)["ContentLength"]
    with _ProgressBar(total=size, desc="B2") as pbar:
        client.download_file(bucket, filename, str(dest),
                             Callback=lambda n: pbar.update(n))
    log.info(f"Downloaded: {_GREEN}{dest}{_RESET}")
    return dest


def download_from_s3(filename):
    client = make_s3_client()
    bucket = os.environ["AWS_BUCKET_NAME"]
    dest = Path.cwd() / filename

    log.info("Downloading from S3: s3://%s/%s", bucket, filename)
    size = client.head_object(Bucket=bucket, Key=filename)["ContentLength"]
    with _ProgressBar(total=size, desc="S3") as pbar:
        client.download_file(bucket, filename, str(dest),
                             Callback=lambda n: pbar.update(n))
    log.info(f"Downloaded: {_GREEN}{dest}{_RESET}")
    return dest


def download(filename):
    try:
        return download_from_b2(filename)
    except Exception as e:
        log.warning("B2 download failed: %s", e)
        log.info("Trying S3...")
        try:
            return download_from_s3(filename)
        except Exception as e:
            log.error("S3 download also failed: %s", e)
            sys.exit(1)


def _test_bucket(label, make_client, bucket):
    test_key = ".encb-write-test"
    results = {}

    try:
        client = make_client()
        client.head_bucket(Bucket=bucket)
        log.info(f"  {label} ({bucket}): {_GREEN}READ OK{_RESET}")
        results["read"] = True
    except Exception as e:
        log.error("  %s READ FAILED: %s", label, e)
        results["read"] = False

    try:
        client = make_client()
        client.put_object(Bucket=bucket, Key=test_key, Body=b"")
        client.delete_object(Bucket=bucket, Key=test_key)
        log.info(f"  {label} ({bucket}): {_GREEN}WRITE OK{_RESET}")
        results["write"] = True
    except Exception as e:
        log.error("  %s WRITE FAILED: %s", label, e)
        results["write"] = False

    return all(results.values())


def test_connectivity():
    ok = True

    log.info("Testing S3 connectivity...")
    ok = _test_bucket("S3", make_s3_client, os.environ["AWS_BUCKET_NAME"]) and ok

    log.info("Testing B2 connectivity...")
    ok = _test_bucket("B2", make_b2_client, os.environ["B2_BUCKET_NAME"]) and ok

    if ok:
        log.info(f"{_GREEN + _BOLD}All connectivity tests passed.{_RESET}")
    else:
        log.error("Some connectivity tests failed.")
    return ok


def main():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(
        description="Encrypted backup: create GPG-encrypted tar.gz and upload to B2/S3",
        epilog="""\
env variables (set via --env or export):
  B2_KEY_ID              Backblaze B2 key ID
  B2_APPLICATION_KEY     Backblaze B2 application key
  B2_BUCKET_NAME         Backblaze B2 bucket name
  B2_BUCKET_ENDPOINT     Backblaze B2 S3-compatible endpoint URL

  AWS_ACCESS_KEY         AWS access key ID
  AWS_SECRET_KEY         AWS secret access key
  AWS_REGION             AWS region (default: us-east-1)
  AWS_BUCKET_NAME        AWS S3 bucket name
  AWS_STORAGE_CLASS      S3 storage class (e.g. STANDARD, GLACIER)
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version",
                        version="%(prog)s 1.0.0")
    parser.add_argument("--env", metavar="PATH",
                        help="Load env vars from file (KEY=VALUE per line)")
    parser.add_argument("--name", metavar="NAME",
                        help="Custom name for archive (encb-<name>-<ts>.tar.gz.gpg)")
    parser.add_argument("--download", metavar="FILENAME",
                        help="Download file from B2/S3 instead of uploading")
    parser.add_argument("--from-b2", action="store_true",
                        help="Download from B2 only (fail if not found)")
    parser.add_argument("--from-aws", action="store_true",
                        help="Download from S3 only (fail if not found)")
    parser.add_argument("--skip-b2", action="store_true",
                        help="Skip upload to Backblaze B2")
    parser.add_argument("--skip-aws", action="store_true",
                        help="Skip upload to AWS S3")
    parser.add_argument("--test-connectivity", action="store_true",
                        help="Only test read/write access to B2 and S3, then exit")
    parser.add_argument("paths", nargs="*",
                        help="Files or directories to include in the backup")
    args = parser.parse_args()

    if args.env:
        load_env_file(args.env)

    required_b2 = ["B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME",
                    "B2_BUCKET_ENDPOINT"]
    required_s3 = ["AWS_ACCESS_KEY", "AWS_SECRET_KEY", "AWS_BUCKET_NAME"]

    if args.test_connectivity:
        check_required(*required_b2, *required_s3)
        ok = test_connectivity()
        sys.exit(0 if ok else 1)

    if args.download:
        if args.from_b2 and args.from_aws:
            log.error("--from-b2 and --from-aws are mutually exclusive")
            sys.exit(1)

        if args.from_b2:
            check_required(*required_b2)
            try:
                download_from_b2(args.download)
            except Exception as e:
                log.error("B2 download failed: %s", e)
                sys.exit(1)
        elif args.from_aws:
            check_required(*required_s3)
            try:
                download_from_s3(args.download)
            except Exception as e:
                log.error("S3 download failed: %s", e)
                sys.exit(1)
        else:
            check_required(*required_b2, *required_s3)
            download(args.download)
        return

    if not args.paths:
        log.error("at least one path is required")
        sys.exit(1)

    if not args.name:
        log.error("--name is required when uploading")
        sys.exit(1)

    validate_paths(args.paths)

    check_required(*required_b2, *required_s3)

    passphrase = read_passphrase()

    ts = make_timestamp()
    archive = create_archive(args.paths, ts, passphrase, name=args.name)

    if not args.skip_b2:
        try:
            upload_to_b2(archive)
        except Exception as e:
            log.error("B2 upload failed: %s", e)

    if not args.skip_aws:
        try:
            upload_to_s3(archive)
        except Exception as e:
            log.error("S3 upload failed: %s", e)


if __name__ == "__main__":
    main()
