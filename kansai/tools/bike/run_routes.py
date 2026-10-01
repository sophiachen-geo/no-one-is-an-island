import json, sys, collections, math
from route import Graph, alternatives, length, hav, shared, ekey
import profile as P
SHRINES = {   # main hall coordinates (checked against kmc refs / Wikidata in points.toml where present)
    "hongu": ("熊野本宮大社", 135.7735, 33.8404),
    "hayatama": ("熊野速玉大社", 135.9837, 33.7323),
    "nachi": ("熊野那智大社", 135.8901, 33.6688),
}
roads = json.load(open("roads.json"))
G = Graph(roads)
print("ways kept", len(G.ways), "rejected", dict(G.rejected), "nodes", len(G.xy), file=sys.stderr)
# largest connected component only (snap targets must be in it)
comp = {}; cid = 0
und = collections.defaultdict(set)
for u, lst in G.adj.items():
    for v, *_ in lst: und[u].add(v); und[v].add(u)
for s in list(und):
    if s in comp: continue
    cid += 1; st = [s]; comp[s] = cid
    while st:
        u = st.pop()
        for v in und[u]:
            if v not in comp: comp[v] = cid; st.append(v)
size = collections.Counter(comp.values()); main = size.most_common(1)[0][0]
print("components", len(size), "main size", size[main], file=sys.stderr)
snap = {}
for k, (nm, lo, la) in SHRINES.items():
    d, n = G.nearest(lo, la, pred=lambda n: comp.get(n) == main)
    snap[k] = n
    print(k, nm, "snap", round(d, 1), "m", G.xy[n], file=sys.stderr)
pairs = [("hongu", "hayatama"), ("hayatama", "nachi"), ("nachi", "hongu")]
out = {"osm_base": roads["osm3s"], "snap": {k: [G.xy[n][0], G.xy[n][1]] for k, n in snap.items()}, "pairs": {}}
for a, b in pairs:
    kept, base = alternatives(G, snap[a], snap[b])
    res = []
    for path, edges in kept:
        st, pts, h = P.stats(G, edges)
        st["coords"] = [[round(x, 6), round(y, 6)] for x, y, *_ in pts[::5]]
        st["h"] = [round(v, 1) for v in h[::5]]
        st["cum"] = [round(p[2], 1) for p in pts[::5]]
        st["edges"] = [[u, v, w] for u, v, w, L in edges]
        res.append(st)
        print(a, b, round(st["len_m"] / 1000, 2), "km up", round(st["up_m"]), "down", round(st["down_m"]), "max", round(st["max_grade_200m"], 1), "tunnels", sum(1 for r in st["structures"] if r["kind"] == "tunnel"), [r[0] for r in st["refs"][:5]], file=sys.stderr)
    out["pairs"][a + "-" + b] = res
json.dump(out, open("routes_out.json", "w"), ensure_ascii=False)
