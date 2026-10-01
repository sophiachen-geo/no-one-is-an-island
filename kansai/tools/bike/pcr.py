"""How much of each corridor runs on the 太平洋岸自転車道 (Pacific Coast Cycling Road): the length of the corridor's own
OpenStreetMap line within 30 m of the route line in MLIT 近畿地方整備局's KML (Route_wakayama.kml, Route_mie.kml from
https://www.kkr.mlit.go.jp/road/pcr/map/). The KML is used for this overlap only; its line is not exported or drawn.
Adds pcr_m to every corridor in corridors.json."""
import json, re, os
from shapely.geometry import LineString
from shapely.ops import unary_union
from pyproj import Transformer
from route import Graph
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
R = os.environ.get("BIKE_RESEARCH", os.path.join(os.getcwd(), "..", "research", "bike"))
lines = []
for fn in ("pcr_mlit_Route_wakayama.kml", "pcr_mlit_Route_mie.kml"):
    s = open(os.path.join(R, fn), encoding="utf-8").read()
    for c in re.findall(r"<coordinates>(.*?)</coordinates>", s, re.S):
        pts = [tuple(map(float, p.split(",")[:2])) for p in c.split()]
        if len(pts) > 1: lines.append(LineString([TR(*p) for p in pts]))
PCR = unary_union(lines).buffer(30)
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("corridors.json"))
tot = 0
for r in C:
    L = LineString([TR(*G.xy[n]) for n in r["nodes"]])
    ov = L.intersection(PCR).length
    r["pcr_m"] = round(ov)
    if ov > 200: print(r["id"], r["len_m"], "on PCR", round(ov), r["refs"][:2]); tot += ov
json.dump(C, open("corridors.json", "w"), ensure_ascii=False)
print("total on PCR (all corridors)", round(tot))
