#!/usr/bin/env python3
"""Download the latest Sonora release for Linux into ~/.local/bin."""

import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RELEASES_URL = "https://api.github.com/repos/sonorahq/sonora/releases/latest"


def get_latest_asset(architecture: str) -> tuple[str, str]:
    """Return the latest release tag and matching Linux binary URL."""
    command = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--retry",
        "3",
        "--header",
        "Accept: application/vnd.github+json",
        "--header",
        "User-Agent: update-sonora-python-script",
        RELEASES_URL,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    release = json.loads(result.stdout)
    tag = release["tag_name"]
    expected_name = f"sonora-{tag}-{architecture}-unknown-linux-gnu"

    for asset in release.get("assets", []):
        if asset.get("name") == expected_name:
            return tag, asset["browser_download_url"]

    available = ", ".join(asset.get("name", "?") for asset in release.get("assets", []))
    raise RuntimeError(
        f"Latest release {tag} has no {architecture} Linux binary. "
        f"Available assets: {available or 'none'}"
    )


def update_sonora() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("This updater supports Linux releases only.")

    if not shutil.which("curl"):
        raise RuntimeError("curl is required but was not found in PATH.")

    architecture = platform.machine()
    print("Checking the latest Sonora release...", flush=True)
    tag, asset_url = get_latest_asset(architecture)

    target = Path.home() / ".local" / "bin" / "sonora"
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".sonora-", dir=target.parent, delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)

        print(f"Downloading Sonora {tag} to {target}...", flush=True)
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--retry",
                "3",
                "--show-error",
                "--progress-bar",
                "--output",
                str(temp_path),
                asset_url,
            ],
            stdout=sys.stdout,
            stderr=sys.stdout,
            check=True,
        )

        if temp_path.stat().st_size == 0:
            raise RuntimeError("The downloaded file is empty.")

        temp_path.chmod(0o755)
        temp_path.replace(target)
        print(f"Installed Sonora {tag} at {target}")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    try:
        update_sonora()
    except subprocess.CalledProcessError as error:
        print(f"curl failed with exit code {error.returncode}.", file=sys.stderr)
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        return error.returncode or 1
    except (json.JSONDecodeError, KeyError, OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
