#!/usr/bin/env python3
"""Enrich prices.json with real plat values from warframe.market.
SLOW: rate-limited to 3 req/sec.
Caches results in wm_prices_cache.json (24h validity).
FIXED: Validates slugs against market catalog before fetching.
"""
import json, os, sys, time, urllib.request
from pathlib import Path

WFINFO_DIR = str(Path(__file__).parent)
PRICES   = os.path.join(WFINFO_DIR, "prices.json")
FILTERED = os.path.join(WFINFO_DIR, "filtered_items.json")
CACHE    = os.path.join(WFINFO_DIR, "wm_prices_cache.json")
SLUGS_CACHE = os.path.join(WFINFO_DIR, "market_slugs_cache.json")
BLACKLIST_FILE = os.path.join(WFINFO_DIR, "market_blacklist.json")
CACHE_MAX_HOURS = 24
RATE_DELAY = 0.35

def get_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "wfinfo-ng/1.0",
        "Accept": "application/json",
        "Language": "en",
        "Platform": "pc"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def url_name(part):
    s = part.lower()
    for ch in (" ", "-", "&"):
        s = s.replace(ch, "_")
    return s.replace("'", "").replace("__", "_").strip("_")

def load_valid_slugs():
    if os.path.exists(SLUGS_CACHE):
        try:
            c = json.load(open(SLUGS_CACHE))
            age_h = (time.time() - c.get("timestamp", 0)) / 3600
            if age_h < CACHE_MAX_HOURS:
                slugs = set(c.get("slugs", []))
                print(f"Loaded {len(slugs)} cached market slugs ({age_h:.1f}h old)")
                return slugs
        except Exception:
            pass
    print("Fetching market item catalog from warframe.market...")
    try:
        # v1/items was retired (404) - v2 has a different response shape:
        # {"data": [{"slug": ..., ...}]} instead of {"payload": {"items": [...]}}
        # with "url_name". The per-item statistics endpoint (fetch_price)
        # is still on v1 and works fine, so only this catalog fetch moved.
        data = get_json("https://api.warframe.market/v2/items")
        items = data.get("data", [])
        slugs = set(item["slug"] for item in items if "slug" in item)
        print(f"Fetched {len(slugs)} valid slugs")
        with open(SLUGS_CACHE, "w") as f:
            json.dump({"timestamp": time.time(), "slugs": list(slugs)}, f)
        return slugs
    except Exception as e:
        print(f"WARNING: Could not fetch market catalog: {e}", file=sys.stderr)
        return set()

def median(values):
    s = sorted(values)
    if not s: return 0.0
    n = len(s)
    return float(s[n//2]) if n % 2 else (s[n//2-1] + s[n//2]) / 2.0

def fetch_price(part_name, valid_slugs):
    un = url_name(part_name)
    if valid_slugs and un not in valid_slugs:
        return None, "delisted"
    try:
        url = f"https://api.warframe.market/v1/items/{un}/statistics"
        data = get_json(url)
        stats = data.get("payload", {}).get("statistics_closed", {}).get("90days", [])
        if not stats:
            return None, "no_data"
        prices = [s.get("median") for s in stats if s.get("median")]
        return (median(prices) if prices else None), "ok"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "404"
        return None, f"http_{e.code}"
    except Exception as e:
        return None, f"error_{e}"

def load_blacklist():
    """Load items from the blacklist file."""
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE) as bf:
                blacklist = set(json.load(bf))
            print(f"Loaded {len(blacklist)} blacklisted items")
            return blacklist
        except Exception as e:
            print(f"WARNING: Could not load blacklist: {e}", file=sys.stderr)
    return set()

def main():
    if not os.path.exists(FILTERED):
        sys.exit("Need filtered_items.json - run synthesis first")

    # Load blacklisted items to skip silently
    blacklist = load_blacklist()

    valid_slugs = load_valid_slugs()

    f = json.load(open(FILTERED))
    names = set()
    for eq in f["eqmt"].values():
        for p in eq["parts"]:
            names.add(p)
            if eq["type"] in ("Warframes", "Archwing") and not p.endswith(" Blueprint"):
                names.add(f"{p} Blueprint")
    for era in f["relics"].values():
        for r in era.values():
            for slot in ("rare1","uncommon1","uncommon2","common1","common2","common3"):
                if r.get(slot):
                    names.add(r[slot])
    names = sorted(names)
    print(f"Need prices for {len(names)} items")

    cache = {}
    if os.path.exists(CACHE):
        try:
            c = json.load(open(CACHE))
            age_h = (time.time() - c.get("timestamp", 0)) / 3600
            if age_h < CACHE_MAX_HOURS:
                cache = c.get("prices", {})
                print(f"Loaded cache ({len(cache)} entries, {age_h:.1f}h old)")
            else:
                print(f"Cache stale ({age_h:.1f}h) - will refetch")
        except Exception:
            pass

    todo = [n for n in names if n not in cache]
    print(f"Cached: {len(names)-len(todo)}. Fetching: {len(todo)} (~{len(todo)*RATE_DELAY/60:.1f}min)")

    start = time.time()
    fetched = failed = skipped = 0
    for i, name in enumerate(todo):
        # Check blacklist before making any API call
        if name in blacklist:
            skipped += 1
            continue

        price, status = fetch_price(name, valid_slugs)
        if status == "delisted":
            skipped += 1
        elif price is not None:
            cache[name] = price
            fetched += 1
        else:
            failed += 1

        if (i+1) % 25 == 0 or i == len(todo)-1:
            elapsed = time.time() - start
            eta = elapsed / (i+1) * (len(todo)-i-1) if i < len(todo)-1 else 0
            print(f"  {i+1}/{len(todo)} ({fetched} ok, {failed} failed, {skipped} skipped) - ETA {eta:.0f}s")

        with open(CACHE, "w") as cf:
            json.dump({"timestamp": time.time(), "prices": cache}, cf, indent=2)
        time.sleep(RATE_DELAY)

    prices_list = [{"name": n, "custom_avg": float(cache.get(n, 0.0))} for n in sorted(names)]
    backup = PRICES + ".before-enrich"
    if os.path.exists(PRICES):
        os.rename(PRICES, backup)
    with open(PRICES, "w") as pf:
        json.dump(prices_list, pf, indent=2)
    with_price = sum(1 for p in prices_list if p["custom_avg"] > 0)
    print(f"\nWrote {PRICES}: {with_price}/{len(prices_list)} items have real prices")
    print(f"Skipped {skipped} delisted items, {failed} other failures")
    print(f"Backup: {backup}")

if __name__ == "__main__":
    main()
