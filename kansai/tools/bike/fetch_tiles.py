import json, sys, os
from fetch import run
# corridor 33.60-33.90 N, 135.70-136.06 E split into 3 x 3 tiles; every way intersecting a tile is returned whole
lat = [33.60, 33.70, 33.80, 33.90]; lon = [135.70, 135.82, 135.94, 136.06]
Q = '[out:json][timeout:300];way["highway"]["highway"!~"^(proposed|construction|abandoned|platform|raceway|bus_stop|elevator|corridor|via_ferrata|razed|disused)$"]({s},{w},{n},{e});out body geom qt;'
os.makedirs("tiles", exist_ok=True)
for i in range(3):
    for j in range(3):
        f = f"tiles/roads_{i}{j}.json"
        if os.path.exists(f): continue
        run(Q.format(s=lat[i], w=lon[j], n=lat[i + 1], e=lon[j + 1]), f)
ways = {}; base = []
for i in range(3):
    for j in range(3):
        d = json.load(open(f"tiles/roads_{i}{j}.json"))
        base.append(d["osm3s"]["timestamp_osm_base"])
        for e in d["elements"]:
            ways[e["id"]] = e
json.dump({"osm3s": {"timestamp_osm_base": min(base), "timestamps": sorted(set(base))}, "elements": list(ways.values())}, open("roads.json", "w"))
print("roads.json", len(ways), min(base), max(base), file=sys.stderr)
