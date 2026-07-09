#!/usr/bin/env python3
"""
relic_recommend_watcher.py - watches EE.log for the relic-selection screen
(Navigation console, before a Void Fissure mission) and writes a ranked list
of your OWNED relics (by expected plat value for your NEED list) to a state
file that overlay.py's RelicRecommendOverlay reads. Hides again once you
confirm a relic pick.

Trigger lines (found empirically in EE.log):
- Open:  "ThemedProjectionManager.lua: PopulateInventoryGrid"
- Close: "Dialog::CreateOkCancel(description=Are you sure you want to equip"
"""
import glob
import json
import time
from pathlib import Path

from paths import DATA_DIR, WFINFO_DIR
STATE_FILE = DATA_DIR / "relic-recommend.json"
LOG_FILE = DATA_DIR / "relic-recommend-watcher.log"
CRAFTED_PARTS_FILE = DATA_DIR / "crafted_parts.json"

# EE.log path resolved via paths.py (reads config.json override or auto-detects)
def _get_ee_log_path():
    try:
        from paths import get_ee_log_path
        return str(get_ee_log_path() or "")
    except Exception:
        return str(
            Path.home() / ".local/share/Steam/steamapps/compatdata/230410/pfx"
            "/drive_c/users/steamuser/AppData/Local/Warframe/EE.log"
        )

OPEN_MARKER = "ThemedProjectionManager.lua: PopulateInventoryGrid"
CLOSE_MARKER = "Dialog::CreateOkCancel(description=Are you sure you want to equip"

POLL_INTERVAL = 1.0

INTACT_CHANCES = {"Rare": 0.0203, "Uncommon": 0.1100, "Common": 0.2533}
RARITY_FIELDS = {
    "rare1": "Rare",
    "uncommon1": "Uncommon", "uncommon2": "Uncommon",
    "common1": "Common", "common2": "Common", "common3": "Common",
}


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def _is_crafted(part, crafted):
    if part in crafted:
        return True
    if part.endswith(" Blueprint"):
        return part[: -len(" Blueprint")] in crafted
    return (part + " Blueprint") in crafted


def compute_recommendations(limit=8):
    """Rank your OWNED relics by expected plat value for your NEED list."""
    filt = _load_json(WFINFO_DIR / "filtered_items.json", {})
    owned_parts = _load_json(WFINFO_DIR / "owned_items.json", {})
    owned_relics = _load_json(WFINFO_DIR / "owned_relics.json", {})
    prices_list = _load_json(WFINFO_DIR / "prices.json", [])
    prices = {
        p["name"]: float(p.get("custom_avg") or 0)
        for p in prices_list if isinstance(p, dict) and "name" in p
    }
    crafted = set(_load_json(CRAFTED_PARTS_FILE, []))

    results = []
    for era, relics in filt.get("relics", {}).items():
        for rname, relic in relics.items():
            owned_count = owned_relics.get(f"{era} {rname}", {}).get("owned", 0)
            if owned_count <= 0:
                continue
            ev_total = ev_need = 0.0
            need_parts = []
            for field, rarity in RARITY_FIELDS.items():
                part = relic.get(field)
                if not part:
                    continue
                cnt = owned_parts.get(part, owned_parts.get(part + " Blueprint", 0))
                cnt = cnt if isinstance(cnt, int) else 0
                plat = prices.get(part, prices.get(part + " Blueprint", 0))
                ev = INTACT_CHANCES[rarity] * plat
                ev_total += ev
                if cnt <= 0 and not _is_crafted(part, crafted):
                    ev_need += ev
                    need_parts.append(part)
            results.append({
                "era": era, "name": rname, "owned": owned_count,
                "ev_total": round(ev_total, 1), "ev_need": round(ev_need, 1),
                "need_parts": need_parts,
            })
    results.sort(key=lambda r: -r["ev_need"])
    return results[:limit]


def find_ee_log():
    p = _get_ee_log_path()
    if p and Path(p).exists():
        return p
    return None


def _write_state(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data))


def main():
    log("=== relic recommend watcher started ===")
    ee_log_path = find_ee_log()
    if not ee_log_path:
        log("ERROR: EE.log not found")
        return

    f = open(ee_log_path, "r", errors="ignore")
    f.seek(0, 2)  # start at end - only react to new lines from here on

    while True:
        line = f.readline()
        if not line:
            try:
                cur_size = Path(ee_log_path).stat().st_size
            except OSError:
                cur_size = 0
            if cur_size < f.tell():
                log("EE.log truncated/rotated, reopening")
                f.close()
                f = open(ee_log_path, "r", errors="ignore")
            time.sleep(POLL_INTERVAL)
            continue

        if OPEN_MARKER in line:
            log("relic selection screen opened")
            recs = compute_recommendations()
            _write_state({
                "visible": True,
                "timestamp": int(time.time()),
                "relics": recs,
            })
        elif CLOSE_MARKER in line:
            log("relic confirmed, hiding overlay")
            _write_state({"visible": False, "timestamp": int(time.time())})


if __name__ == "__main__":
    main()