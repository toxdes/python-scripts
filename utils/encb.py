#!/usr/bin/env -S uv run
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
import io
import logging
import os
import shlex
import subprocess
import sys
import tarfile
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


def run_cmd(cmd):
    log.info("%s[+]%s %s", _CYAN + _BOLD, _RESET,
             " ".join(shlex.quote(str(c)) for c in cmd))
    subprocess.run(cmd, check=True)


def create_archive(paths, ts, name=None):
    if name:
        prefix = f"encb-{name}-{ts}"
    else:
        prefix = f"encb-{ts}"
    gpg_name = f"{prefix}.tar.gz.gpg"

    log.info("Building tar.gz in memory...")
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        for p in paths:
            src = Path(p).resolve()
            log.info("[+] adding %s", src)
            tar.add(str(src), arcname=f"{prefix}/{src.name}")

    tar_data = tar_buf.getvalue()
    log.info("tar.gz size: %d bytes", len(tar_data))

    final_path = Path.cwd() / gpg_name
    log.info("%s[+]%s gpg --symmetric ... -o %s", _CYAN + _BOLD, _RESET, final_path)
    gpg = subprocess.run(
        ["gpg", "--symmetric", "--cipher-algo", "AES256",
         "--s2k-cipher-algo", "AES256",
         "--s2k-digest-algo", "SHA512",
         "--s2k-count", "65011712",
         "--compress-algo", "none",
         "--output", str(final_path)],
        input=tar_data,
        check=True,
    )

    log.info("%sArchive created: %s%s", _GREEN + _BOLD, _RESET, final_path)
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

    extra = {}
    if storage_class:
        extra["StorageClass"] = storage_class

    log.info("Uploading to S3 bucket %s (storage class: %s)...",
             bucket, storage_class)
    client.upload_file(
        str(archive_path),
        bucket,
        archive_path.name,
        ExtraArgs=extra,
    )
    log.info("%sUploaded to S3: s3://%s/%s%s",
             _GREEN, bucket, archive_path.name, _RESET)


def upload_to_b2(archive_path):
    client = make_b2_client()
    bucket = os.environ["B2_BUCKET_NAME"]

    log.info("Uploading to B2 bucket %s...", bucket)
    client.upload_file(
        str(archive_path),
        bucket,
        archive_path.name,
    )
    log.info("%sUploaded to B2: b2://%s/%s%s",
             _GREEN, bucket, archive_path.name, _RESET)


def download_from_b2(filename):
    client = make_b2_client()
    bucket = os.environ["B2_BUCKET_NAME"]
    dest = Path.cwd() / filename

    log.info("Downloading from B2: b2://%s/%s", bucket, filename)
    client.download_file(bucket, filename, str(dest))
    log.info("%sDownloaded: %s%s", _GREEN, dest, _RESET)
    return dest


def download_from_s3(filename):
    client = make_s3_client()
    bucket = os.environ["AWS_BUCKET_NAME"]
    dest = Path.cwd() / filename

    log.info("Downloading from S3: s3://%s/%s", bucket, filename)
    client.download_file(bucket, filename, str(dest))
    log.info("%sDownloaded: %s%s", _GREEN, dest, _RESET)
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
        log.info("  %s (%s): %sREAD OK%s", label, bucket, _GREEN, _RESET)
        results["read"] = True
    except Exception as e:
        log.error("  %s READ FAILED: %s", label, e)
        results["read"] = False

    try:
        client = make_client()
        client.put_object(Bucket=bucket, Key=test_key, Body=b"")
        client.delete_object(Bucket=bucket, Key=test_key)
        log.info("  %s (%s): %sWRITE OK%s", label, bucket, _GREEN, _RESET)
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
        log.info("%sAll connectivity tests passed.%s", _GREEN + _BOLD, _RESET)
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
    parser.add_argument("--env", metavar="PATH",
                        help="Load env vars from file (KEY=VALUE per line)")
    parser.add_argument("--name", metavar="NAME",
                        help="Custom name for archive (encb-<name>-<ts>.tar.gz.gpg)")
    parser.add_argument("--download", metavar="FILENAME",
                        help="Download file from B2/S3 instead of uploading")
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
        check_required(*required_b2, *required_s3)
        download(args.download)
        return

    if not args.paths:
        log.error("at least one path is required")
        sys.exit(1)

    validate_paths(args.paths)

    check_required(*required_b2, *required_s3)

    ts = make_timestamp()
    archive = create_archive(args.paths, ts, name=args.name)

    try:
        upload_to_b2(archive)
    except Exception as e:
        log.error("B2 upload failed: %s", e)

    try:
        upload_to_s3(archive)
    except Exception as e:
        log.error("S3 upload failed: %s", e)


if __name__ == "__main__":
    main()
