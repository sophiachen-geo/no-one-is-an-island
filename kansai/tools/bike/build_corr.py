import json, collections, sys, math, os
from route import Graph, hav
import metrics as M
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("chains.json"))
P = json.load(open(os.path.join(os.getcwd(), "..", "geo", "osm", "places.json")))
places = []
for e in P.get("elements", []):
    t = e.get("tags", {}); pl = t.get("place")
    if pl not in ("city", "town", "village", "hamlet", "suburb", "neighbourhood", "quarter", "isolated_dwelling", "locality"): continue
    lo = e.get("lon") or (e.get("center") or {}).get("lon"); la = e.get("lat") or (e.get("center") or {}).get("lat")
    if lo is None: continue
    places.append((lo, la, t.get("name"), t.get("name:en") or t.get("name:ja-Latn") or t.get("name:ja_rm"), pl))
def name_of(n):
    p = G.xy[n]
    best = min(places, key=lambda q: hav(p, (q[0], q[1])) * (1.0 if q[4] in ("village", "hamlet", "town", "suburb", "neighbourhood", "quarter") else 1.6))
    return best[2], best[3], round(hav(p, (best[0], best[1])))
SH = {v: k for k, v in C["snap"].items()}
out = []
for i, ch in enumerate(C["chains"]):
    pts = M.densify(G, ch)
    raw, fx, hp, kind, src = M.heights(G, pts)
    L = pts[-1][2]
    refs = collections.Counter(); hw = collections.Counter(); surf = collections.Counter()
    for a, b in zip(ch, ch[1:]):
        w = next((ww for v, LL, ww, k in G.adj[a] if v == b), None) or next((ww for v, LL, ww, k in G.adj[b] if v == a), None)
        t = G.ways[w].get("tags", {}); l = hav(G.xy[a], G.xy[b])
        refs[t.get("ref") or ""] += l; hw[t.get("highway")] += l; surf[t.get("surface") or "?"] += l
    r = {"id": i, "a": ch[0], "b": ch[-1], "a_name": SH.get(ch[0]) or name_of(ch[0]), "b_name": SH.get(ch[-1]) or name_of(ch[-1]),
         "len_m": round(L), "h_a": round(hp[0], 1), "h_b": round(hp[-1], 1), "h_max": round(max(hp), 1), "h_min": round(min(hp), 1),
         "up5": [round(x) for x in M.climb(hp, 5)], "up_lo": [round(x) for x in M.climb(hp, 10)], "up_hi": [round(x) for x in M.climb([x for x in fx], 2)], "up5_line": [round(x) for x in M.climb(fx, 5)],
         "gmax": [round(x, 1) if isinstance(x, float) else x for x in M.grade_max(pts, hp)], "structures": M.structures(G, pts, kind),
         "refs": [(k, round(v)) for k, v in refs.most_common(4)], "hw": {k: round(v) for k, v in hw.items()}, "surf": {k: round(v) for k, v in surf.items()},
         "dem": dict(src), "nodes": ch, "prof": [[round(p[2]), round(h, 1)] for p, h in zip(pts, hp)]}
    out.append(r)
    tn = [s for s in r["structures"] if s["kind"] == "tunnel"]
    print(i, r["a_name"] if isinstance(r["a_name"], str) else r["a_name"][0], "→", r["b_name"] if isinstance(r["b_name"], str) else r["b_name"][0], f'{L/1000:.1f} km', "h", r["h_a"], "→", r["h_b"], "max", r["h_max"], "up/down(5m)", r["up5"], "range", r["up_lo"], r["up_hi"], "gmax", r["gmax"][0], "tun", len(tn), sum(s["len"] for s in tn), r["refs"][:2], file=sys.stderr)
json.dump(out, open("corridors.json", "w"), ensure_ascii=False)
