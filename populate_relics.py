#!/usr/bin/env python3
"""Build owned_relics.json from inventory using authoritative WFCD mapping.

Fetches fresh relic uniqueName -> (era, code) mapping from WFCD on each run.
Falls back to cached relic_name_mapping.json if the fetch fails (offline mode).
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

from paths import WFINFO_DIR
INV = WFINFO_DIR / "inventory.json"
FILT = WFINFO_DIR / "filtered_items.json"
CACHE = WFINFO_DIR / "relic_name_mapping.json"
OUT = WFINFO_DIR / "owned_relics.json"
WFCD_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/Relics.json"

REFINEMENTS = ('Bronze', 'Silver', 'Gold', 'Platinum')
REFINEMENT_WORDS = {'Intact', 'Exceptional', 'Flawless', 'Radiant'}
TIERS = {'Lith', 'Meso', 'Neo', 'Axi'}


def fetch_mapping():
    """Try to download fresh data from WFCD. Returns dict or None."""
    try:
        print(f"Fetching WFCD relics from {WFCD_URL}")
        with urllib.request.urlopen(WFCD_URL, timeout=20) as r:
            relics = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        print(f"  fetch failed: {e}")
        return None

    mapping = {}
    for r in relics:
        if not isinstance(r, dict):
            continue
        uname = str(r.get('uniqueName', ''))
        name = str(r.get('name', ''))
        if not uname.startswith('/Lotus/Types/Game/Projections/'):
            continue
        base = uname
        for suf in REFINEMENTS:
            if base.endswith(suf):
                base = base[:-len(suf)]
                break
        parts = name.split()
        if parts and parts[-1] in REFINEMENT_WORDS:
            parts = parts[:-1]
        if len(parts) >= 2 and parts[0] in TIERS:
            mapping[base] = [parts[0], ' '.join(parts[1:])]
    print(f"  got {len(mapping)} relics")
    return mapping


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    mapping = fetch_mapping()
    if mapping:
        CACHE.write_text(json.dumps(mapping, indent=2))
        print(f"  cached to {CACHE.name}")
    else:
        mapping = load_cache()
        if not mapping:
            print("ERROR: no fresh data and no cache. Run once with internet.")
            return
        print(f"  using cached mapping ({len(mapping)} relics)")

    mapping = {k: tuple(v) for k, v in mapping.items()}

    inv = json.loads(INV.read_text())
    filt = json.loads(FILT.read_text())

    owned_by_base = {}
    for item in inv.get('MiscItems', []):
        itype = item.get('ItemType', '')
        if 'VoidProjection' not in itype:
            continue
        base = itype
        for suf in REFINEMENTS:
            if base.endswith(suf):
                base = base[:-len(suf)]
                break
        owned_by_base[base] = owned_by_base.get(base, 0) + item.get('ItemCount', 0)

    counts_by_code = {}
    unmapped = []
    for base, count in owned_by_base.items():
        code = mapping.get(base)
        if code:
            counts_by_code[code] = counts_by_code.get(code, 0) + count
        else:
            unmapped.append((base, count))

    out = {}
    for tier, sub in filt.get('relics', {}).items():
        for code, info in sub.items():
            rewards = [info.get(k, '') for k in ('rare1','uncommon1','uncommon2','common1','common2','common3') if info.get(k)]
            out[f"{tier} {code}"] = {
                "owned": counts_by_code.get((tier, code), 0),
                "vaulted": info.get('vaulted', False),
                "rewards": rewards,
            }

    OUT.write_text(json.dumps(out, indent=2))

    owned_codes = sum(1 for v in out.values() if v['owned'] > 0)
    total_inv = sum(owned_by_base.values())
    total_mapped = sum(v['owned'] for v in out.values())
    print(f"\nResults:")
    print(f"  Inventory prefixes: {len(owned_by_base)} ({len(owned_by_base)-len(unmapped)} mapped)")
    print(f"  Total relics: {total_inv} ({total_mapped} mapped)")
    print(f"  Relic codes with owned > 0: {owned_codes} / {len(out)}")
    if unmapped:
        print(f"  Unmapped (likely new/special types):")
        for base, cnt in unmapped[:8]:
            print(f"    {base} (x{cnt})")


if __name__ == "__main__":
    main()
