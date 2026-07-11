#!/usr/bin/env python3
"""Build crafted_parts.json from inventory mastery + manual marks.
A part is 'crafted' if you have the Prime item it builds in your inventory
(Suits/LongGuns/etc or have XP on it), OR if you've manually marked it
crafted via the missing-parts tracker."""
import json
from pathlib import Path
from paths import DATA_DIR, WFINFO_DIR
INV = WFINFO_DIR / "inventory.json"
WFCD = WFINFO_DIR / "wfcd_all_cache.json"
ITEMS = WFINFO_DIR / "filtered_items.json"
MANUAL = DATA_DIR / "crafted-before.json"
OUT = DATA_DIR / "crafted_parts.json"

inv = json.loads(INV.read_text())
wfcd = json.loads(WFCD.read_text())
items_data = json.loads(ITEMS.read_text())

path_to_name = {}
items_list = wfcd if isinstance(wfcd, list) else wfcd.get("items", [])
for item in items_list:
    if isinstance(item, dict):
        u, n = item.get("uniqueName"), item.get("name")
        if u and n:
            path_to_name[u] = n

paths = set()
for cat in ["Suits", "LongGuns", "Pistols", "Melee", "SpaceSuits", "SpaceGuns",
            "SpaceMelee", "Sentinels", "SentinelWeapons", "MechSuits"]:
    for it in inv.get(cat, []) or []:
        if isinstance(it, dict):
            p = it.get("ItemType")
            if p:
                paths.add(p)
for it in inv.get("XPInfo", []) or []:
    if isinstance(it, dict):
        p = it.get("ItemType")
        if p and it.get("XP", 0) > 0:
            paths.add(p)

eq_names = set()
for p in paths:
    n = path_to_name.get(p)
    if n and "Prime" in n:
        eq_names.add(n)

auto_crafted = set()
for eq_name in eq_names:
    eq = items_data.get("eqmt", {}).get(eq_name)
    if not eq:
        continue
    for pname in eq.get("parts", {}):
        auto_crafted.add(pname)

try:
    manual = set(json.loads(MANUAL.read_text()))
except (OSError, json.JSONDecodeError):
    manual = set()

all_crafted = sorted(auto_crafted | manual)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_crafted))

print(f"Mastered/owned Prime equipment: {len(eq_names)}")
print(f"Auto-detected crafted parts:    {len(auto_crafted)}")
print(f"Manual marks:                   {len(manual)}")
print(f"Total crafted parts:            {len(all_crafted)}")
print(f"Written: {OUT}")