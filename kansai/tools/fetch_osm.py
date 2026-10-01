"""Fetch OpenStreetMap layers for the Kansai/Shingu maps via Overpass (writes osm/*.json).

Data (c) OpenStreetMap contributors, ODbL. The kumi.systems mirror is used because it accepts
large bbox queries; queries are retried on 504.
"""
import json, os, sys, time, urllib.request, urllib.parse
os.makedirs("osm", exist_ok=True)
EP = "https://overpass.kumi.systems/api/interpreter"
BB = "33.38,135.25,34.45,136.42"      # S,W,N,E  the map sheet
CITY = "33.60,135.70,33.95,136.08"    # Shingu window for local roads and water areas
Q = {
 "coast":   f'[out:json][timeout:180];way["natural"="coastline"]({BB});out geom;',
 "rivers":  f'[out:json][timeout:180];way["waterway"="river"]({BB});out geom;',
 "roads":   f'[out:json][timeout:180];(way["highway"~"^(motorway|trunk|motorway_link|trunk_link)$"]({BB});way["highway"="primary"]({BB}););out geom;',
 "rail":    f'[out:json][timeout:180];way["railway"="rail"]({BB});out geom;',
 "routes":  f'[out:json][timeout:180];relation["route"~"^(hiking|foot|pilgrimage)$"]({BB});out geom;',
 "places":  f'[out:json][timeout:180];node["place"~"^(city|town|village|suburb|quarter|neighbourhood|hamlet)$"]({BB});out;',
 "pois":    f'[out:json][timeout:180];(nwr["amenity"~"^(townhall|hospital)$"]({BB});nwr["railway"="station"]({BB});nwr["waterway"="dam"]({BB});nwr["name"~"ダム$"]({BB});nwr["amenity"="place_of_worship"]["name"~"熊野|神倉|大斎原|那智|速玉|本宮|補陀洛|花の窟|玉置"]({BB});nwr["natural"="waterfall"]({BB});nwr["natural"="peak"]["ele"]({BB}););out center tags;',
 "city_roads": f'[out:json][timeout:180];way["highway"~"^(secondary|tertiary)$"]({CITY});out geom;',
 "city_water": f'[out:json][timeout:180];(way["natural"="water"]({CITY});relation["natural"="water"]({CITY});way["waterway"="riverbank"]({CITY}););out geom;',
}
# Path networks for the Kumano Kodō courses that 11_routes_kodo.py rebuilds, fetched in tiles small enough for the
# public mirrors. A mirror whose data lag OpenStreetMap by more than MAX_LAG_DAYS is skipped for the next one.
MIRRORS = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter",
           "https://overpass.private.coffee/api/interpreter", EP]
MAX_LAG_DAYS = 3
HW_OKU = "^(path|footway|track|steps|bridleway|unclassified|residential|tertiary|secondary|primary|service)$"   # primary: the street through Yoshinoyama
HW_OHE = "^(path|footway|track|steps|unclassified|tertiary|secondary|primary|trunk)$"
HW_ISE = "^(path|footway|track|steps|bridleway|unclassified|residential|living_street|service|tertiary|secondary|primary|trunk)$"
TRAILS = {   # name: (highway filter, [S, W, N, E tiles])
 "trail_okugake": (HW_OKU, [(33.82, 135.74, 34.10, 136.00), (34.10, 135.74, 34.38, 136.00)]),
 "trail_ohechi": (HW_OHE, [(33.44, 135.36, 33.60, 135.51), (33.60, 135.36, 33.76, 135.51), (33.44, 135.51, 33.53, 135.66), (33.53, 135.51, 33.62, 135.66),
                          (33.42, 135.66, 33.50, 135.81), (33.50, 135.66, 33.58, 135.81), (33.44, 135.81, 33.57, 135.96), (33.57, 135.81, 33.70, 135.96)]),
 "trail_iseji": (HW_ISE, [(34.15, 136.18, 34.45, 136.42), (33.98, 136.10, 34.15, 136.32), (33.84, 135.98, 33.98, 136.20), (33.70, 135.95, 33.84, 136.06),
                          (33.78, 135.74, 33.92, 135.98)]),
}
NAMED = {    # named old-road ways the router prefers: (filter, area), fetched like the trail tiles
 "route_okugake": ('way["highway"]["name"~"奥駈|奥駆"]', (33.82, 135.74, 34.38, 136.00)),
 "route_ohechi": ('way["highway"]["name"~"熊野古道|大辺路|長井坂|富田坂|仏坂"]', (33.42, 135.36, 33.76, 135.96)),
}


def overpass(q, tries=None):
    """Run q on the first mirror that answers with data no older than MAX_LAG_DAYS; returns the parsed JSON."""
    import datetime as dt
    last = None
    for attempt in range(tries or 3 * len(MIRRORS)):
        ep = MIRRORS[attempt % len(MIRRORS)]
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "no-one-is-an-island kansai map build"})
            with urllib.request.urlopen(req, timeout=600) as r:
                js = json.loads(r.read())
            if "error" in js.get("remark", "").lower():
                raise RuntimeError(js["remark"][:200])
            base = dt.datetime.fromisoformat(js["osm3s"]["timestamp_osm_base"].replace("Z", "+00:00"))
            lag = (dt.datetime.now(dt.timezone.utc) - base).days
            if lag > MAX_LAG_DAYS:
                raise RuntimeError(f"data {lag} days old ({base:%Y-%m-%d})")
            print("  ", ep.split("/")[2], js["osm3s"]["timestamp_osm_base"], len(js["elements"]), flush=True)
            return js
        except Exception as e:
            last = e; print("   retry", attempt, ep.split("/")[2], repr(e)[:160], flush=True); time.sleep(5 * (attempt + 1))
    raise last


def fetch_tile(hw, s, w, n, e, depth=0, flt=None):
    """One tile of a trail set (or of a named-way filter `flt`). A tile every mirror times out on (dense towns, long
    name searches) is fetched as four quarters, down to a 64th; ways that cross the cuts are kept once."""
    sel = flt or f'way["highway"~"{hw}"]'
    q = f'[out:json][timeout:300];{sel}({s},{w},{n},{e});out geom qt;'
    try:
        return overpass(q, tries=len(MIRRORS) if depth < 3 else None)
    except Exception:
        if depth >= 3: raise
    ms, mw = round((s + n) / 2, 5), round((w + e) / 2, 5)
    print(f"   splitting ({s}, {w}, {n}, {e})", flush=True)
    parts = [fetch_tile(hw, *b, depth + 1, flt=flt) for b in ((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e))]
    seen, els = set(), []
    for p in parts:
        for el in p["elements"]:
            if (el["type"], el["id"]) not in seen: seen.add((el["type"], el["id"])); els.append(el)
    return {"elements": els, "osm3s": {"timestamp_osm_base": min(p["osm3s"]["timestamp_osm_base"] for p in parts)}}


if "--trails" in sys.argv:                 # python3 fetch_osm.py --trails [iseji okugake …]: all sets, or the named ones
    only = [a for a in sys.argv[sys.argv.index("--trails") + 1:] if not a.startswith("-")]
    for name, (hw, tiles) in TRAILS.items():
        if only and not any(o in name for o in only): continue
        if os.path.exists(f"osm/{name}.json"):
            print(name, "cached"); continue
        out, base = {"elements": []}, []
        for i, (s, w, n, e) in enumerate(tiles):
            part = f"osm/{name}.part{i}.json"           # tiles are kept until the set is complete, so a rerun resumes
            if not os.path.exists(part):
                json.dump(fetch_tile(hw, s, w, n, e), open(part, "w"))
            js = json.load(open(part))
            out["elements"] += js["elements"]; base.append(js["osm3s"]["timestamp_osm_base"])
        out["osm_base"] = sorted(base)        # one stamp per tile
        json.dump(out, open(f"osm/{name}.json", "w")); print(name, len(out["elements"]), "ways", flush=True)
        for i in range(len(tiles)): os.remove(f"osm/{name}.part{i}.json")
    for name, (flt, (s, w, n, e)) in NAMED.items():
        if only and not any(o in name for o in only): continue
        if os.path.exists(f"osm/{name}.json"):
            print(name, "cached"); continue
        js = fetch_tile(None, s, w, n, e, flt=flt); json.dump(js, open(f"osm/{name}.json", "w")); print(name, len(js["elements"]), "ways", flush=True)
    sys.exit(0)

for k in (sys.argv[1:] or Q):
    if os.path.exists(f"osm/{k}.json"):
        print(k, "cached"); continue
    for attempt in range(6):
        try:
            data = urllib.parse.urlencode({"data": Q[k]}).encode()
            req = urllib.request.Request(EP, data=data, headers={"User-Agent": "no-one-is-an-island kansai map build"})
            with urllib.request.urlopen(req, timeout=400) as r:
                raw = r.read()
            js = json.loads(raw)
            json.dump(js, open(f"osm/{k}.json", "w"))
            print(k, len(js.get("elements", [])), f"{len(raw)/1e6:.1f}MB", flush=True)
            break
        except Exception as e:
            print(k, "attempt", attempt, "error", e, flush=True)
            time.sleep(5 * (attempt + 1))
