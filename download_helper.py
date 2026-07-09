#!/usr/bin/env python3
"""
download_helper.py — Download warframe-api-helper and orbiter binaries.

Downloads:
1. warframe-api-helper from Sainan's GitHub releases
2. orbiter (Rust OCR detector) from GoblinOfChaos/Kieda-s-Orbiter releases

Called automatically by install.py / install.sh if the binaries are missing.
Can also be run manually: python download_helper.py

Usage:
    python download_helper.py           # Download both binaries
    python download_helper.py --force   # Force re-download even if present
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
API_HELPER_REPO = "Sainan/warframe-api-helper"
ORBITER_REPO = "GoblinOfChaos/Kieda-s-Orbiter"
GITHUB_API_HELPER = f"https://api.github.com/repos/{API_HELPER_REPO}/releases/latest"
GITHUB_API_ORBITER = f"https://api.github.com/repos/{ORBITER_REPO}/releases/latest"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Expected asset names per platform
API_HELPER_ASSET_NAME = {
    "win32": "warframe-api-helper.exe",
    "linux": "Linux.Ubuntu.22.04+.zip",
}

ORBITER_ASSET_NAME = {
    "win32": "orbiter-windows-x86_64.exe",
    "linux": "orbiter-linux-x86_64",
}

# Expected output paths per platform
API_HELPER_OUTPUT_PATH = {
    "win32": WFINFO_DIR / "warframe-api-helper.exe",
    "linux": WFINFO_DIR / "warframe-api-helper",
}

ORBITER_OUTPUT_PATH = {
    "win32": WFINFO_DIR / "orbiter.exe",
    "linux": WFINFO_DIR / "orbiter",
}


def _get_latest_release(repo: str) -> dict:
    """Fetch latest release info from GitHub API."""
    api_url = GITHUB_API_HELPER if repo == API_HELPER_REPO else GITHUB_API_ORBITER
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "kiedas-orbiter/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _download_binary(url: str, dest: Path):
    """Download binary from URL."""
    print(f"  Downloading {dest.name}...", flush=True)
    tmp = dest.with_suffix(".tmp")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    tmp.write_bytes(data)
    tmp.replace(dest)
    print(f"  Saved to {dest}")


def download_api_helper(force: bool = False) -> bool:
    """
    Download warframe-api-helper for the current platform.
    Returns True if downloaded, False if already present (and not forced).
    """
    platform = sys.platform
    if platform not in API_HELPER_ASSET_NAME:
        print(f"  No helper binary available for platform: {platform}")
        print("  Inventory features will not work.")
        return False

    asset_name = API_HELPER_ASSET_NAME[platform]
    output = API_HELPER_OUTPUT_PATH[platform]

    if output.exists() and not force:
        print(f"  {output.name} already present — skipping download.")
        print("  Run with --force to re-download.")
        return False

    print(f"Fetching latest warframe-api-helper release...")
    try:
        release = _get_latest_release(API_HELPER_REPO)
    except Exception as e:
        print(f"  ERROR: could not fetch release info: {e}")
        return False

    version = release.get("tag_name", "?")
    print(f"  Latest version: {version}")

    # Find the matching asset
    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == asset_name), None)
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
            binary = next(
                (n for n in names if "warframe-api-helper" in n and not n.endswith("/")), None
            )
            if not binary:
                print(f"  ERROR: could not find binary in zip. Contents: {names}")
                return False
            output.write_bytes(zf.read(binary))
        # Make executable
        output.chmod(output.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  Extracted to {output}")
    else:
        _download_binary(url, output)
        if not IS_WINDOWS:
            output.chmod(output.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"  warframe-api-helper {version} installed.")
    return True


def download_orbiter(force: bool = False) -> bool:
    """
    Download orbiter binary for the current platform.
    Returns True if downloaded, False if already present (and not forced).
    """
    platform = sys.platform
    if platform not in ORBITER_ASSET_NAME:
        print(f"  No orbiter binary available for platform: {platform}")
        return False

    asset_name = ORBITER_ASSET_NAME[platform]
    output = ORBITER_OUTPUT_PATH[platform]

    if output.exists() and not force:
        print(f"  {output.name} already present — skipping download.")
        print("  Run with --force to re-download.")
        return False

    print(f"Fetching orbiter release from Kieda-s-Orbiter...")
    try:
        release = _get_latest_release(ORBITER_REPO)
    except Exception as e:
        print(f"  ERROR: could not fetch orbiter release info: {e}")
        return False

    version = release.get("tag_name", "?")
    print(f"  Latest version: {version}")

    # Find the matching asset
    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == asset_name), None)
    if not asset:
        print(f"  ERROR: orbiter asset '{asset_name}' not found in release {version}")
        print(f"  Available: {[a['name'] for a in assets]}")
        return False

    url = asset["browser_download_url"]

    _download_binary(url, output)

    # Make executable on Linux
    if IS_LINUX:
        output.chmod(output.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"  orbiter {version} installed.")
    return True


def download_helper(force: bool = False) -> dict:
    """
    Download both warframe-api-helper and orbiter binaries.
    Returns a dict with success status for each component:
    {'api_helper': bool, 'orbiter': bool}
    """
    print("Downloading binaries...", flush=True)

    api_helper_success = download_api_helper(force=force)
    orbiter_success = download_orbiter(force=force)

    print()
    if api_helper_success and orbiter_success:
        print(f"  {BOLD}Both binaries downloaded successfully.{RESET}")
    elif api_helper_success:
        print(f"  ⚠️  warframe-api-helper downloaded, but orbiter missing.")
        print("      Relic reward OCR overlay won't work until orbiter is installed.")
    else:
        print(f"  ⚠️  warframe-api-helper missing. Inventory features won't work.")

    return {
        "api_helper": api_helper_success,
        "orbiter": orbiter_success,
    }


if __name__ == "__main__":
    force = "--force" in sys.argv
    result = download_helper(force=force)
    
    # Exit with non-zero if any binary failed to download
    if not (result["api_helper"] and result["orbiter"]):
        sys.exit(1)
    sys.exit(0)
