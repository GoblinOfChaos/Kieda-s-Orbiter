#!/usr/bin/env python3
"""
Convert warframe-api-helper's inventory.json into wfinfo-ng's owned_items.json.
v2: uses relics dict for canonical drop_names; emits NEED entries with count 0.
"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from paths import WFINFO_DIR

WFCD_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/All.json"
CACHE_PATH = WFINFO_DIR / "wfcd_all_cache.json"
FILTERED_PATH = WFINFO_DIR / "filtered_items.json"
RELIC_SLOTS = ("rare1", "uncommon1", "uncommon2", "common1", "common2")


def log(msg):
    print(msg, file=sys.stderr)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_wfcd():
    log(f"Downloading WFCD items data from {WFCD_URL} (~40 MB, one-time)...")
    req = Request(WFCD_URL, headers={"User-Agent": "wfinfo-ng-ownership/1.0"})
    try:
        with urlopen(req, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except URLError as e:
        log(f"  ERROR: download failed: {e}")
        sys.exit(1)
    data = json.loads(payload)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    log(f"  Cached {len(data)} items.")
    return data


def load_wfcd():
    if CACHE_PATH.exists():
        size_mb = CACHE_PATH.stat().st_size // (1024 * 1024)
        log(f"Using cached WFCD data ({size_mb} MB).")
        return load_json(CACHE_PATH)
    return fetch_wfcd()


def collect_drop_names(filtered):
    """All prime parts. For warframe-like gear (Chassis/Neuroptics/Systems),
    also emit '<part> Blueprint' since the relic drop is the BP form."""
    import sys
    names = set()
    indicators = ("Chassis", "Neuroptics", "Systems")
    wf_count = 0
    for gear_name, gear in filtered.get("eqmt", {}).items():
        if not isinstance(gear, dict):
            continue
        parts = list(gear.get("parts", {}).keys())
        is_wf = any(any(ind in p for ind in indicators) for p in parts)
        if is_wf:
            wf_count += 1
        for part_name in parts:
            names.add(part_name)
            if is_wf and not part_name.endswith("Blueprint"):
                names.add(f"{part_name} Blueprint")
    if "Forma Blueprint" in filtered.get("ignored_items", {}):
        names.add("Forma Blueprint")
    print(f"  Collected {len(names)} drop_names ({wf_count} warframe-like gear).", file=sys.stderr)
    return names


def build_path_to_dropname(wfcd_items, drop_names):
    """path -> list of drop_names. WFCD uses 'Component' suffix on some paths
    where the game inventory uses 'Blueprint'; register both forms."""
    import sys
    mapping = {}
    for item in wfcd_items:
        if not isinstance(item, dict):
            continue
        pname = item.get("name", "")
        puniq = item.get("uniqueName", "")
        if pname in drop_names and puniq:
            mapping.setdefault(puniq, []).append(pname)
        for c in item.get("components", []) or []:
            if not isinstance(c, dict):
                continue
            cn = c.get("name", "")
            cu = c.get("uniqueName", "")
            if not cu:
                continue
            paths_to_try = [cu]
            if cu.endswith("Component"):
                paths_to_try.append(cu[:-len("Component")] + "Blueprint")
            for cand in (
                f"{pname} {cn}".strip(),
                f"{pname} {cn} Blueprint".strip(),
                cn,
            ):
                if cand in drop_names:
                    for path in paths_to_try:
                        if cand not in mapping.get(path, []):
                            mapping.setdefault(path, []).append(cand)
    print(f"  Mapped {len(mapping)} paths.", file=sys.stderr)
    return mapping


def extract_owned(inventory, path_to_dropname, drop_names=None):
    """All drop_names start at 0; bump every name mapped from each matched
    inventory path. (path_to_dropname now returns lists of names per path.)"""
    owned = {name: 0 for name in (drop_names or [])}
    categories = ("MiscItems", "Recipes", "Consumables")
    for cat in categories:
        items = inventory.get(cat, [])
        if not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            path = entry.get("ItemType", "")
            count = int(entry.get("ItemCount", 0))
            for name in path_to_dropname.get(path, []):
                owned[name] = owned.get(name, 0) + count
    return owned


def main():
    if len(sys.argv) != 3:
        log("Usage: populate_owned.py inventory.json owned_items.json")
        sys.exit(1)
    inv_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not inv_path.exists():
        log(f"ERROR: {inv_path} not found.")
        sys.exit(1)
    if not FILTERED_PATH.exists():
        log(f"ERROR: {FILTERED_PATH} not found. Run ./update.sh first.")
        sys.exit(1)

    log("Loading inventory and filtered_items.json...")
    inventory = load_json(inv_path)
    filtered = load_json(FILTERED_PATH)

    log("Building drop_name set from current relics...")
    drop_names = collect_drop_names(filtered)

    log("Loading WFCD item data...")
    wfcd_items = load_wfcd()

    log("Building path -> drop_name mapping...")
    path_to_dropname = build_path_to_dropname(wfcd_items, drop_names)

    coverable = {n for names in path_to_dropname.values() for n in names}
    uncovered = drop_names - coverable
    if uncovered:
        log(f"  WARNING: {len(uncovered)} drop_names have no WFCD path mapping.")
        log("  These will always show as NEED. Examples:")
        for n in sorted(uncovered)[:5]:
            log(f"    {n}")

    log("Extracting owned counts from inventory...")
    owned = extract_owned(inventory, path_to_dropname, drop_names)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(owned, f, indent=2, sort_keys=True)

    have = sum(1 for v in owned.values() if v > 0)
    need = sum(1 for v in owned.values() if v == 0)
    log(f"Wrote {out_path}:")
    log(f"  OWNED (count > 0): {have}")
    log(f"  NEED  (count = 0): {need}")
    log(f"  Total tracked:     {len(owned)}")


if __name__ == "__main__":
    main()
