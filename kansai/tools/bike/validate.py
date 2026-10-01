import json, math, sys, statistics as stt
from route import Graph, hav
import profile as P, elev, gsi_pts
roads = json.load(open("roads.json")); G = Graph(roads)
d = json.load(open("routes_out.json"))
sel = [("hongu-hayatama", 0), ("hayatama-nachi", 0), ("nachi-hongu", 1), ("nachi-hongu", 3), ("hongu-hayatama", 1)]
allres = []
for pair, i in sel:
    edges = [(u, v, w, hav(G.xy[u], G.xy[v])) for u, v, w in d["pairs"][pair][i]["edges"]]
    pts = P.densify(G, edges)
    kind = [P.structure(G.ways[w].get("tags", {})) for *_, w in pts]
    raw, ben, off, srcs = elev.profile(pts)
    med = elev.median_filter(ben, 2)
    tiles = sorted({gsi_pts.tile_of(p[0], p[1]) for p in pts})
    gp = gsi_pts.points_in_tiles(tiles)
    errs = {"raw": [], "bench": [], "bench_med": []}; rows = []
    for lon, lat, alt, kd in gp:
        # nearest sample
        best = min(range(len(pts)), key=lambda k: (pts[k][0] - lon) ** 2 + ((pts[k][1] - lat) * 1.2) ** 2)
        dist = hav((pts[best][0], pts[best][1]), (lon, lat))
        if dist > 15 or kind[best]: continue
        rows.append((kd, alt, raw[best], ben[best], med[best], round(dist, 1)))
        if raw[best] is not None: errs["raw"].append(raw[best] - alt)
        errs["bench"].append(ben[best] - alt); errs["bench_med"].append(med[best] - alt)
    def summ(e):
        if not e: return "n=0"
        a = [abs(x) for x in e]
        return f"n={len(e)} median|e|={stt.median(a):.2f} mean e={stt.mean(e):+.2f} max|e|={max(a):.1f}"
    print(pair, i, "points within 15 m:", len(rows), "| tiles", len(tiles))
    for k, e in errs.items(): print("   ", k, summ(e))
    for r in rows[:12]: print("      ", r)
    up_raw = P.climb([x for x in raw if x is not None]); up_b = P.climb(ben); up_m = P.climb(med)
    print("    climb raw", [round(x) for x in up_raw], "bench", [round(x) for x in up_b], "bench+median", [round(x) for x in up_m])
    allres.append((pair, i, rows))
json.dump(allres, open("validate_rows.json", "w"))
