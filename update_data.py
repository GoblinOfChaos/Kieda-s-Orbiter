#!/usr/bin/env python3
"""
update_data.py — cross-platform replacement for update.sh.

Fetches prices.json and filtered_items.json from api.warframestat.us.
Keeps the existing file untouched if the fetch fails or doesn't return
valid JSON — same "safe fetch" behavior update.sh had via curl+jq, just
without depending on either of those being installed (neither ships with
Windows, and jq in particular isn't a Python/pip dependency this project
already has).
"""
import json
import sys
import urllib.request
from pathlib import Path

WFINFO_DIR = Path(__file__).parent

SOURCES = [
    ("https://api.warframestat.us/wfinfo/prices/", WFINFO_DIR / "prices.json"),
    ("https://api.warframestat.us/wfinfo/filtered_items/", WFINFO_DIR / "filtered_items.json"),
]


def safe_fetch(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kiedas-orbiter/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                print(f"WARNING: {url} returned HTTP {r.status} — keeping existing {dest.name}", file=sys.stderr)
                return False
            data = json.loads(r.read())
    except Exception as e:
        print(f"WARNING: {url} failed ({e}) — keeping existing {dest.name}", file=sys.stderr)
        return False

    dest.write_text(json.dumps(data))
    print(f"Updated {dest.name} from {url}")
    return True


def main():
    ok = True
    for url, dest in SOURCES:
        if not safe_fetch(url, dest):
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
