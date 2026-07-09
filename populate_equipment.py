#!/usr/bin/env python3
"""
populate_equipment.py - Builds non-prime equipment tracking data.
Sources: WFCD warframe-items per-category JSONs + All.json (for necramechs).
Cross-references with inventory.json for mastery status.
"""
import json, sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from paths import DATA_DIR, WFINFO_DIR
INVENTORY_FILE = WFINFO_DIR / "inventory.json"
OUTPUT_FILE    = DATA_DIR / "equipment_status.json"
CACHE_FILE     = WFINFO_DIR / "equipment_data_cache.json"
ALL_JSON_CACHE = WFINFO_DIR / "wfcd_all_cache.json"

WFCD_BASE = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json"

# (tab_name, fetcher_config, [inventory_keys_for_mastery])
TAB_CONFIG = [
    ("Warframe",        {"files": ["Warframes.json"]},          ["Suits"]),
    ("Primary",         {"files": ["Primary.json"]},            ["LongGuns"]),
    ("Secondary",       {"files": ["Secondary.json"]},          ["Pistols"]),
    ("Melee",           {"files": ["Melee.json"]},              ["Melee"]),
    ("Archwing",        {"files": ["Archwing.json",
                                   "Arch-Gun.json",
                                   "Arch-Melee.json"]},         ["SpaceSuits", "SpaceGuns", "SpaceMelee"]),
    ("Necramech",       {"all_filter": "mech"},                 ["MechSuits"]),
    ("Sentinel",        {"files": ["Sentinels.json"]},          ["Sentinels"]),
    ("Sentinel Weapon", {"files": ["SentinelWeapons.json"]},    ["SentinelWeapons"]),
    ("Pet",             {"files": ["Pets.json"]},               ["KubrowPets"]),
]

def fetch_json(url, what):
    try:
        req = Request(url, headers={"User-Agent": "wfinfo-ng"})
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except (URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
        print(f"    WARN: could not fetch {what}: {e}", file=sys.stderr)
        return None

def load_all_json():
    if ALL_JSON_CACHE.exists():
        try:
            sz_mb = ALL_JSON_CACHE.stat().st_size // 1024 // 1024
            print(f"  Using cached All.json ({sz_mb} MB)")
            return json.loads(ALL_JSON_CACHE.read_text())
        except Exception as e:
            print(f"  Cache corrupted ({e}), refetching")
    print("  Fetching All.json (~52 MB, one-time)...")
    data = fetch_json(f"{WFCD_BASE}/All.json", "All.json")
    if data is not None:
        ALL_JSON_CACHE.write_text(json.dumps(data))
        print(f"  Cached at {ALL_JSON_CACHE}")
    return data

def filter_mechs(all_data):
    if not all_data:
        return []
    out = []
    for item in all_data:
        cat = item.get("category") or ""
        pc  = item.get("productCategory") or ""
        typ = item.get("type") or ""
        if any("Mech" in x for x in (cat, pc, typ)):
            out.append(item)
    return out

def is_prime(name, unique=""):
    return "Prime" in name or "Prime" in unique

def collect_mastered(inventory, keys):
    """Set of uniqueNames the user has (in inventory or has XP > 0).
       XPInfo bleeds across categories but we intersect against actual
       WFCD items for this tab, so cross-bleed is harmless."""
    out = set()
    for k in keys:
        for entry in (inventory.get(k) or []):
            u = entry.get("ItemType", "")
            if u:
                out.add(u)
    for entry in (inventory.get("XPInfo") or []):
        u = entry.get("ItemType", "")
        if u and entry.get("XP", 0) > 0:
            out.add(u)
    return out

def shape_drop(d):
    return {
        "type":     d.get("type", "") or d.get("source", ""),
        "location": d.get("location", "") or d.get("place", ""),
        "rotation": d.get("rotation", ""),
        "rarity":   d.get("rarity", ""),
        "chance":   d.get("chance", 0),
    }

def _base_unique(unique: str) -> str:
    """Return the base (non-prime) uniqueName for a warframe.
    e.g. /Lotus/Powersuits/Frost/FrostPrime -> /Lotus/Powersuits/Frost/Frost"""
    if unique.endswith('Prime'):
        return unique[:-5]  # strip trailing 'Prime'
    # e.g. /Lotus/Powersuits/Frost/FrostPrime
    import re
    return re.sub(r'Prime$', '', unique)


def build_item(raw, tab, mastered, subsumed_set=None):
    unique = raw.get("uniqueName", "")
    components = []
    for c in (raw.get("components") or []):
        components.append({
            "name":  c.get("name", ""),
            "count": c.get("itemCount", 1),
            "drops": [shape_drop(d) for d in (c.get("drops") or [])],
        })
    # Check helminth subsume: look at both exact unique and base version
    subsumed = False
    if subsumed_set and tab == "Warframe":
        base = _base_unique(unique)
        subsumed = (unique in subsumed_set) or (base in subsumed_set)
    return {
        "name":        raw.get("name", ""),
        "uniqueName":  unique,
        "tab":         tab,
        "mastered":    unique in mastered,
        "subsumed":    subsumed,
        "components":  components,
        "itemDrops":   [shape_drop(d) for d in (raw.get("drops") or [])],
        "buildPrice":  raw.get("buildPrice"),
        "marketCost":  raw.get("marketCost"),
        "bpCost":      raw.get("bpCost"),
        "masteryReq":  raw.get("masteryReq", 0),
        "wikiaUrl":    raw.get("wikiaUrl", ""),
        "imageName":   raw.get("imageName", ""),
    }

def main():
    if not INVENTORY_FILE.exists():
        print(f"ERROR: {INVENTORY_FILE} missing. Run refresh first.", file=sys.stderr)
        sys.exit(1)

    inventory = json.loads(INVENTORY_FILE.read_text())

    # Build set of subsumed warframe uniqueNames from InfestedFoundry.ConsumedSuits
    subsumed_set = set()
    try:
        inf_foundry = inventory.get('InfestedFoundry', {})
        for entry in inf_foundry.get('ConsumedSuits', []):
            s = entry.get('s', '')
            if s:
                subsumed_set.add(s)
    except Exception:
        pass
    print(f"  Subsumed warframes: {len(subsumed_set)}")

    cache = {}
    tabs = {}
    all_json = None

    print("=" * 60)
    for tab_name, cfg, inv_keys in TAB_CONFIG:
        print(f"\n[{tab_name}]")
        mastered = collect_mastered(inventory, inv_keys)

        items, seen = [], set()

        if "files" in cfg:
            for fname in cfg["files"]:
                data = fetch_json(f"{WFCD_BASE}/{fname}", fname)
                if data is None:
                    continue
                cache[fname] = data
                kept = 0
                for raw in data:
                    u = raw.get("uniqueName", "")
                    name = raw.get("name", "")
                    if not u or u in seen:
                        continue
                    # Skip Helminth specifically — it's a system, not a masterable warframe
                    if u == "/Lotus/Powersuits/PowersuitAbilities/Helminth":
                        continue
                    seen.add(u)
                    items.append(build_item(raw, tab_name, mastered, subsumed_set))
                    kept += 1
                print(f"  {fname}: kept {kept}")

        if "all_filter" in cfg:
            if all_json is None:
                all_json = load_all_json()
            mechs = filter_mechs(all_json)
            print(f"  All.json mech filter: {len(mechs)} candidates")
            kept = 0
            for raw in mechs:
                u = raw.get("uniqueName", "")
                name = raw.get("name", "")
                if not u or u in seen:
                    continue
                seen.add(u)
                items.append(build_item(raw, tab_name, mastered, subsumed_set))
                kept += 1
            print(f"    kept {kept}")

        items.sort(key=lambda x: (x["mastered"], x["name"].lower()))
        n_mast = sum(1 for x in items if x["mastered"])
        tabs[tab_name] = items
        print(f"  -> {len(items)} items, {n_mast} mastered, {len(items) - n_mast} missing")

    CACHE_FILE.write_text(json.dumps(cache))
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(tabs, indent=2))

    print("\n" + "=" * 60)
    print("Summary:")
    for t in tabs:
        n = len(tabs[t]); m = sum(1 for x in tabs[t] if x["mastered"])
        print(f"  {t:18s} {n:4d} items, {m:4d} mastered, {n-m:4d} missing")

if __name__ == "__main__":
    main()