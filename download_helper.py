#!/usr/bin/env python3
"""
download_helper.py — Download the correct warframe-api-helper binary
for the current platform from Sainan's GitHub releases.

Called automatically by install.py / install.sh if the binary is missing.
Can also be run manually: python download_helper.py
"""

import hashlib
import json
import os
import shutil
import stat
import sys
import urllib.request
from pathlib import Path

WFINFO_DIR = Path(__file__).parent
HELPER_REPO = "Sainan/warframe-api-helper"
GITHUB_API  = f"https://api.github.com/repos/{HELPER_REPO}/releases/latest"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")

# Expected asset names per platform
ASSET_NAME = {
    "win32":  "warframe-api-helper.exe",
    "linux":  "Linux.Ubuntu.22.04+.zip",
}

# Expected output path per platform
OUTPUT_PATH = {
    "win32":  WFINFO_DIR / "warframe-api-helper.exe",
    "linux":  WFINFO_DIR / "warframe-api-helper",
}


def _get_latest_release() -> dict:
    req = urllib.request.Request(
        GITHUB_API,
        headers={"User-Agent": "kiedas-orbiter/1.0", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _download(url: str, dest: Path, expected_sha256: str = None):
    print(f"  Downloading {dest.name}...", flush=True)
    tmp = dest.with_suffix(".tmp")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    if expected_sha256:
        got = hashlib.sha256(data).hexdigest()
        if got != expected_sha256:
            raise ValueError(f"SHA256 mismatch: expected {expected_sha256}, got {got}")
    tmp.write_bytes(data)
    tmp.replace(dest)
    print(f"  Saved to {dest}")


def download_helper(force: bool = False) -> bool:
    """
    Download warframe-api-helper for the current platform.
    Returns True if downloaded, False if already present (and not forced).
    """
    platform = sys.platform
    if platform not in ASSET_NAME:
        print(f"  No helper binary available for platform: {platform}")
        print("  Inventory features will not work.")
        return False

    asset_name = ASSET_NAME[platform]
    output     = OUTPUT_PATH[platform]

    if output.exists() and not force:
        print(f"  {output.name} already present — skipping download.")
        print("  Run with --force to re-download.")
        return False

    print(f"Fetching latest warframe-api-helper release...")
    try:
        release = _get_latest_release()
    except Exception as e:
        print(f"  ERROR: could not fetch release info: {e}")
        return False

    version = release.get("tag_name", "?")
    print(f"  Latest version: {version}")

    # Find the matching asset
    assets = release.get("assets", [])
    asset  = next((a for a in assets if a["name"] == asset_name), None)
    if not asset:
        print(f"  ERROR: asset '{asset_name}' not found in release {version}")
        print(f"  Available: {[a['name'] for a in assets]}")
        return False

    url = asset["browser_download_url"]

    if IS_LINUX and asset_name.endswith(".zip"):
        # Linux release is a zip — extract the binary from it
        import zipfile, io
        print(f"  Downloading {asset_name}...", flush=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Find the binary inside the zip
            names = zf.namelist()
            binary = next((n for n in names if "warframe-api-helper" in n and not n.endswith("/")), None)
            if not binary:
                print(f"  ERROR: could not find binary in zip. Contents: {names}")
                return False
            output.write_bytes(zf.read(binary))
        # Make executable
        output.chmod(output.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  Extracted to {output}")
    else:
        _download(url, output)
        if not IS_WINDOWS:
            output.chmod(output.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"  warframe-api-helper {version} installed.")
    return True


if __name__ == "__main__":
    force = "--force" in sys.argv
    success = download_helper(force=force)
    sys.exit(0 if success else 1)
