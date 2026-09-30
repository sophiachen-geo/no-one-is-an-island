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
