"""Fetch Shingū City facilities and numbered roads from OpenStreetMap (Overpass) into fac/.

Run from the scratch work directory: python3 $T/fetch_facilities.py  →  fac/facilities_osm.json, fac/roads_osm.json
© OpenStreetMap contributors (ODbL)."""
import json, sys, time, urllib.request, urllib.parse
# Shingū City (新宮市) area: facilities + named/numbered roads
Q = """[out:json][timeout:120];
area["name"="新宮市"]["admin_level"="7"]->.a;
(
 nwr["amenity"~"^(hospital|clinic|doctors|townhall|fire_station|police|school|community_centre|pharmacy)$"](area.a);
 nwr["shop"~"^(supermarket|convenience)$"](area.a);
 nwr["office"="government"](area.a);
 nwr["emergency"="assembly_point"](area.a);
 nwr["amenity"="shelter"](area.a);
);
out center tags;"""
R = """[out:json][timeout:120];
area["name"="新宮市"]["admin_level"="7"]->.a;
way["highway"~"^(trunk|primary|secondary|tertiary|motorway|trunk_link)$"](area.a);
out tags geom;"""
def run(q):
    for i in range(6):
        try:
            req = urllib.request.Request("https://maps.mail.ru/osm/tools/overpass/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "no-one-is-an-island/1.0"})
            return json.load(urllib.request.urlopen(req, timeout=180))
        except Exception as e:
            print("retry", i, e, file=sys.stderr); time.sleep(5 * (i + 1))
f = run(Q); import os; os.makedirs("fac", exist_ok=True)
json.dump(f, open("fac/facilities_osm.json", "w"), ensure_ascii=False)
r = run(R); json.dump(r, open("fac/roads_osm.json", "w"), ensure_ascii=False)
from collections import Counter
c = Counter((e.get("tags", {}).get("amenity") or e.get("tags", {}).get("shop") or e.get("tags", {}).get("office") or e.get("tags", {}).get("emergency")) for e in f["elements"])
print("facilities", len(f["elements"]), c.most_common())
rc = Counter((e["tags"].get("ref"), e["tags"].get("name")) for e in r["elements"])
print("road ways", len(r["elements"])); print(rc.most_common(40))
