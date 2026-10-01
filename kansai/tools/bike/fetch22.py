import json, sys, os, time, urllib.request, urllib.parse
UA = "no-one-is-an-island/kansai-research (github sophiachen-geo)"
EP = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
Q = '[out:json][timeout:180];way["highway"]["highway"!~"^(proposed|construction|abandoned|platform|raceway|bus_stop|elevator|corridor|via_ferrata|razed|disused)$"]({s},{w},{n},{e});out body geom qt;'
lat = [33.80, 33.85, 33.90]; lon = [135.94, 136.00, 136.06]
for i in range(2):
    for j in range(2):
        f = f"tiles/sub22_{i}{j}.json"
        if os.path.exists(f): continue
        for a in range(10):
            try:
                req = urllib.request.Request(EP, data=urllib.parse.urlencode({"data": Q.format(s=lat[i], w=lon[j], n=lat[i+1], e=lon[j+1])}).encode(), headers={"User-Agent": UA})
                d = json.loads(urllib.request.urlopen(req, timeout=240).read())
                json.dump(d, open(f, "w")); print(f, len(d["elements"]), d["osm3s"]["timestamp_osm_base"], flush=True); break
            except Exception as ex:
                print("retry", f, a, repr(ex)[:120], flush=True); time.sleep(10 + 10 * a)
ways = {}
ts = []
for i in range(2):
    for j in range(2):
        d = json.load(open(f"tiles/sub22_{i}{j}.json")); ts.append(d["osm3s"]["timestamp_osm_base"])
        for e in d["elements"]: ways[e["id"]] = e
json.dump({"osm3s": {"timestamp_osm_base": min(ts)}, "elements": list(ways.values())}, open("tiles/roads_22.json.tmp", "w"))
os.replace("tiles/roads_22.json.tmp", "tiles/roads_22.json")
print("tile22 done", len(ways), min(ts), flush=True)
