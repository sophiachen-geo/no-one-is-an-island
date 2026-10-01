import json, sys
from route import Graph
import hazards as H
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("corridors.json"))
layers = {}
for f in (H.landslide, H.flood, H.tsunami):
    layers.update(f()); print("loaded", f.__name__, file=sys.stderr)
for r in C:
    line = [G.xy[n] for n in r["nodes"]]
    r["haz"] = {k: round(H.length_in(line, lay)) for k, lay in layers.items()}
    if r["len_m"] > 1500: print(r["id"], r["len_m"], r["haz"], file=sys.stderr)
json.dump(C, open("corridors.json", "w"), ensure_ascii=False)
