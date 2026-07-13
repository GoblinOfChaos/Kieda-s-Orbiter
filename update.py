#!/usr/bin/env python3
"""
update.py — Cross-platform data updater for Kieda's Orbiter.

Replaces update.sh. Downloads fresh item/price data from warframestat.us.
Works on Linux, Windows, and macOS.

Usage:
    python update.py
"""

import json
import sys
import urllib.request
from pathlib import Path

WFINFO_DIR = Path(__file__).parent

PRICES_URL  = "https://api.warframestat.us/wfinfo/prices/"
ITEMS_URL   = "https://api.warframestat.us/wfinfo/filtered_items/"

HEADERS = {"User-Agent": "kiedas-orbiter/1.1"}

# Sanity check thresholds, in entry count rather than raw byte size - a
# byte-size floor rejects legitimately smaller-but-real responses (seen
# live: warframestat.us returning a valid, real 67KB price list while
# still recovering from an outage, well under the old 500KB assumption,
# but genuinely good data). Entry count actually reflects whether the
# response has real content, not just how verbose its formatting is.
MIN_ENTRIES_PRICES = 50
MIN_ENTRIES_ITEMS  = 20


def _entry_count(parsed) -> int:
    """Count real content, not just top-level shape. prices.json is a flat
    list, so len() works directly - but filtered_items.json is a dict of
    a handful of category keys (relics/eqmt/ignored_items/...) with the
    actual bulk of data nested one level inside each (confirmed live:
    5 top-level keys, but 'eqmt' alone held 162 entries), so len() on the
    dict itself massively undercounts it. Sum the nested container sizes
    instead of just counting top-level keys."""
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        total = 0
        for v in parsed.values():
            if isinstance(v, (list, dict)):
                total += len(v)
            else:
                total += 1
        return total
    return 0


def _download(url: str, dest: Path, min_entries: int) -> bool:
    """Download URL to dest. Returns True on success, False on failure."""
    print(f"  Downloading {dest.name}...", end="", flush=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                print(f" FAIL (HTTP {r.status})")
                return False
            data = r.read()
    except Exception as e:
        print(f" FAIL ({e})")
        return False

    # Validate JSON first, then check it actually has meaningful content -
    # a raw byte-size check can't tell a genuinely smaller-but-real
    # response apart from a truncated/corrupt one, but entry count can.
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        print(f" FAIL (invalid JSON: {e})")
        return False

    count = _entry_count(parsed)
    if count < min_entries:
        print(f" FAIL (too few entries: {count}, expected >={min_entries})")
        return False

    # Backup previous version
    if dest.exists():
        backup = dest.with_suffix(dest.suffix + ".previous")
        dest.rename(backup)

    dest.write_bytes(data)
    print(f" OK ({len(data):,} bytes, {count} entries)")
    return True


def update():
    print("Updating Warframe data files...")
    ok_prices = _download(PRICES_URL, WFINFO_DIR / "prices.json", MIN_ENTRIES_PRICES)
    ok_items  = _download(ITEMS_URL,  WFINFO_DIR / "filtered_items.json", MIN_ENTRIES_ITEMS)

    if ok_prices and ok_items:
        print("\n✓ Data files updated successfully.")
        return 0
    else:
        print("\n! Some files failed to update.")
        print("  The app will use existing data if available.")
        print("  Check your internet connection and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(update())
