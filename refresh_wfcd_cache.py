#!/usr/bin/env python3
"""Refresh wfcd_all_cache.json from WFCD/warframe-items GitHub raw.
This is the SOURCE that feeds api.warframestat.us/items - bypassing the API entirely."""
import json, os, sys, time, urllib.request
from pathlib import Path

URL = 'https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/All.json'
OUT = str(Path(__file__).parent / 'wfcd_all_cache.json')
MIN_SIZE = 10_000_000   # All.json is ~40MB; reject anything < 10MB as suspicious
MAX_AGE_DAYS = 7

def needs_refresh():
    if not os.path.exists(OUT):
        return True, "cache missing"
    age_days = (time.time() - os.path.getmtime(OUT)) / 86400
    if age_days > MAX_AGE_DAYS:
        return True, f"cache is {age_days:.1f} days old"
    return False, f"cache is {age_days:.1f} days old (under {MAX_AGE_DAYS}d threshold)"

def refresh():
    print(f"Fetching {URL}")
    req = urllib.request.Request(URL, headers={'User-Agent': 'wfinfo-ng-cache-refresh/1.0'})
    tmp = OUT + '.new'
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
        total = 0
        while True:
            chunk = r.read(64*1024)
            if not chunk: break
            f.write(chunk); total += len(chunk)
            if total % (1024*1024) < 64*1024:
                print(f"  ...{total//(1024*1024)}MB", end='\r')
    print(f"  downloaded {total:,} bytes        ")
    if total < MIN_SIZE:
        os.remove(tmp); raise SystemExit(f"FAIL: only {total} bytes (need >{MIN_SIZE})")
    # Validate JSON
    try:
        with open(tmp, encoding='utf-8') as f:
            data = json.load(f)
        assert isinstance(data, list) and len(data) > 5000, "wrong shape"
    except Exception as e:
        os.remove(tmp); raise SystemExit(f"FAIL: validation failed - {e}")
    if os.path.exists(OUT):
        os.rename(OUT, OUT + '.previous')
    os.rename(tmp, OUT)
    print(f"OK wrote {OUT} ({len(data):,} items)")

if __name__ == '__main__':
    force = '--force' in sys.argv
    need, reason = needs_refresh()
    if force or need:
        print(f"Refresh: {reason}{' (forced)' if force else ''}")
        refresh()
    else:
        print(f"Skip: {reason}")
