"""Road-bed heights of every corridor vs GSI levelling benchmarks, triangulation points and spot heights within 15 m."""
import json, statistics as st, math, sys
from route import Graph, hav
import metrics as M, gsi_pts
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("corridors.json")); CH = json.load(open("chains.json"))
rows = []
for r in C:
    pts = M.densify(G, CH["chains"][r["id"]])
    prof = r["prof"]
    kind = [M.structure(G.ways[p[3]].get("tags", {})) for p in pts]
    tiles = sorted({gsi_pts.tile_of(p[0], p[1]) for p in pts})
    for lon, lat, alt, kd in gsi_pts.points_in_tiles(tiles):
        k = min(range(len(pts)), key=lambda q: (pts[q][0] - lon) ** 2 + ((pts[q][1] - lat) * 1.2) ** 2)
        d = hav((pts[k][0], pts[k][1]), (lon, lat))
        if d > 15 or kind[k]: continue
        h = prof[min(k, len(prof) - 1)][1]
        rows.append((r["id"], kd, alt, h, h - alt, round(d, 1)))
uniq = {}
for row in rows: uniq[(row[1], row[2])] = row          # a point near two corridors counts once
E = [abs(v[4]) for v in uniq.values()]
by = {}
for v in uniq.values(): by.setdefault(v[1], []).append(abs(v[4]))
out = {"n": len(E), "median_abs": round(st.median(E), 2), "p90_abs": round(sorted(E)[int(0.9 * (len(E) - 1))], 2), "max_abs": round(max(E), 1),
       "by_kind": {k: {"n": len(v), "median_abs": round(st.median(v), 2)} for k, v in by.items()}}
print(json.dumps(out, ensure_ascii=False), file=sys.stderr)
worst = sorted(uniq.values(), key=lambda v: -abs(v[4]))[:5]
for w in worst: print("  worst", w, file=sys.stderr)
json.dump(out, open("validate_final.json", "w"))
