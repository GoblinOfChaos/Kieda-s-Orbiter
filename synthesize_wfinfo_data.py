#!/usr/bin/env python3
"""Synthesize wfinfo's filtered_items.json + prices.json from WFCD cache.
Fallback when api.warframestat.us/wfinfo/* is unreachable.
Prices stubbed at 0 plat (no warframe.market integration here)."""
import json, os, re, sys
from collections import Counter
from pathlib import Path

WFINFO_DIR = str(Path(__file__).parent)
CACHE    = os.path.join(WFINFO_DIR, 'wfcd_all_cache.json')
FILTERED = os.path.join(WFINFO_DIR, 'filtered_items.json')
PRICES   = os.path.join(WFINFO_DIR, 'prices.json')

TYPE_MAP = {'Warframes':'Warframes','Primary':'Primary','Secondary':'Secondary',
            'Melee':'Melee','Sentinels':'Sentinels','Archwing':'Archwing',
            'Arch-Gun':'Arch-Gun','Skins':'Skins'}

def is_relic_part(comp):
    return any('Relic' in d.get('location','') for d in comp.get('drops',[]))

def synthesize():
    if not os.path.exists(CACHE):
        sys.stderr.write(f"ERROR: {CACHE} missing\n"); return False
    print(f"Loading {os.path.getsize(CACHE):,} bytes...")
    cache = json.load(open(CACHE))
    eqmt = {}
    excluded = Counter()
    for item in cache:
        name = item.get('name','')
        cat = item.get('category')
        if cat not in TYPE_MAP or 'Prime' not in name: continue
        comps = item.get('components')
        if not comps: continue
        parts = {}
        for c in comps:
            cn = c.get('name','')
            if not is_relic_part(c):
                excluded[cn] += 1; continue
            key = cn if cn.startswith(name) else f"{name} {cn}"
            parts[key] = {'ducats': int(c.get('ducats',0) or 0)}
        if parts:
            eqmt[name] = {'type': TYPE_MAP[cat],
                          'vaulted': bool(item.get('vaulted',False)),
                          'parts': parts}
    tc = Counter(v['type'] for v in eqmt.values())
    print(f"Equipment: {len(eqmt)} primes - {dict(tc)}")
    if excluded:
        print(f"Filtered non-relic components: {sum(excluded.values())} total. Top:")
        for n,c in excluded.most_common(5): print(f"  '{n}' x{c}")

    relics = {'Lith':{},'Neo':{},'Meso':{},'Axi':{}}
    rx = re.compile(r'^(Lith|Neo|Meso|Axi)\s+([A-Z]+\d+)(?:\s+(Exceptional|Flawless|Radiant))?$')
    vars_ = {}
    for item in cache:
        if item.get('category') != 'Relics': continue
        m = rx.match(item.get('name',''))
        if not m: continue
        era, code, ref = m.groups()
        vars_.setdefault((era,code), {})[ref or 'Intact'] = item
    for (era,code), v in vars_.items():
        it = v.get('Intact') or v.get('Exceptional') or v.get('Flawless') or v.get('Radiant')
        rw = it.get('rewards', [])
        if len(rw) != 6: continue
        s = sorted(rw, key=lambda r: r.get('chance',0))
        relics[era][code] = {'vaulted': bool(it.get('vaulted',False)),
            'rare1':s[0]['item']['name'],
            'uncommon1':s[1]['item']['name'], 'uncommon2':s[2]['item']['name'],
            'common1':s[3]['item']['name'], 'common2':s[4]['item']['name'], 'common3':s[5]['item']['name']}
    print(f"Relics: Lith={len(relics['Lith'])} Neo={len(relics['Neo'])} Meso={len(relics['Meso'])} Axi={len(relics['Axi'])}")

    out = {'errors':[], 'relics':relics, 'eqmt':eqmt, 'ignored_items':{}}
    with open(FILTERED,'w') as f: json.dump(out, f, indent=2)
    print(f"Wrote filtered_items.json: {os.path.getsize(FILTERED):,} bytes")

    names = set()
    for eq in eqmt.values():
        for p in eq['parts']:
            names.add(p)
            if eq['type'] in ('Warframes','Archwing') and not p.endswith(' Blueprint'):
                names.add(f"{p} Blueprint")
    for ed in relics.values():
        for r in ed.values():
            for slot in ('rare1','uncommon1','uncommon2','common1','common2','common3'):
                names.add(r[slot])
    prices = [{'name':n,'custom_avg':0.0} for n in sorted(names)]
    with open(PRICES,'w') as f: json.dump(prices, f, indent=2)
    print(f"Wrote prices.json: {os.path.getsize(PRICES):,} bytes ({len(prices)} items @ 0 plat)")
    return True

if __name__ == '__main__':
    sys.exit(0 if synthesize() else 1)
