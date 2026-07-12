#!/usr/bin/env python3
"""
populate_images.py - Download item images from WFCD CDN for the equipment
tabs and mod cards. Run after populate_equipment.py. Uses 10 parallel
downloads. Caches forever.
"""
import json, sys
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from paths import DATA_DIR, CACHE_DIR

EQUIPMENT_FILE = DATA_DIR / "equipment_status.json"
WFCD_CACHE_FILE = Path(__file__).parent / "wfcd_all_cache.json"
CACHE_DIR      = CACHE_DIR / "item_images"
CDN_URL        = "https://cdn.warframestat.us/img"

def fetch(name):
    if not name:
        return name, "skipped"
    target = CACHE_DIR / name
    if target.exists() and target.stat().st_size > 0:
        return name, "cached"
    try:
        req = Request(f"{CDN_URL}/{name}", headers={"User-Agent": "wfinfo-ng"})
        with urlopen(req, timeout=15) as r:
            data = r.read()
        if data:
            target.write_bytes(data)
            return name, "downloaded"
        return name, "empty"
    except Exception as e:
        return name, f"failed: {type(e).__name__}"

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not EQUIPMENT_FILE.exists():
        print(f"ERROR: {EQUIPMENT_FILE} missing. Run populate_equipment.py first.")
        sys.exit(1)

    data = json.loads(EQUIPMENT_FILE.read_text())
    names = set()
    for tab, items in data.items():
        for item in items:
            if (n := item.get("imageName")):
                names.add(n)

    if WFCD_CACHE_FILE.exists():
        wfcd = json.loads(WFCD_CACHE_FILE.read_text())
        wfcd_items = wfcd if isinstance(wfcd, list) else (wfcd.get("items") or wfcd.get("data") or [])
        for item in wfcd_items:
            if isinstance(item, dict) and item.get("category") == "Mods" and (n := item.get("imageName")):
                names.add(n)

    print(f"Total unique item images: {len(names)}")
    cached = downloaded = failed = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fut in as_completed({ex.submit(fetch, n): n for n in names}):
            name, status = fut.result()
            if status == "cached": cached += 1
            elif status == "downloaded": downloaded += 1
            else:
                failed += 1
                if failed <= 5:
                    print(f"  ! {name}: {status}", file=sys.stderr)

    print(f"\nCached:     {cached}")
    print(f"Downloaded: {downloaded}")
    print(f"Failed:     {failed}")
    print(f"Cache dir:  {CACHE_DIR}")

if __name__ == "__main__":
    main()