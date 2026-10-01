import json, sys
from route import Graph
from plateau import plateaus
exec(open("run_routes.py").read().split("pairs = [")[0].split("roads = json.load")[0])
roads = json.load(open("roads.json")); G = Graph(roads)
import collections
SH = {"hongu": (135.7735, 33.8404), "hayatama": (135.9837, 33.7323), "nachi": (135.8901, 33.6688)}
und = collections.defaultdict(set)
for u, lst in G.adj.items():
    for v, *_ in lst: und[u].add(v); und[v].add(u)
comp = {}; cid = 0
for s in list(und):
    if s in comp: continue
    cid += 1; st = [s]; comp[s] = cid
    while st:
        u = st.pop()
        for v in und[u]:
            if v not in comp: comp[v] = cid; st.append(v)
main = collections.Counter(comp.values()).most_common(1)[0][0]
snap = {k: G.nearest(*v, pred=lambda n: comp.get(n) == main)[1] for k, v in SH.items()}
res = {}
for a, b in [("hongu", "hayatama"), ("hayatama", "nachi"), ("nachi", "hongu")]:
    rs, D = plateaus(G, snap[a], snap[b], S=float(sys.argv[1]) if len(sys.argv) > 1 else 1.5)
    print(a, b, "shortest", round(D / 1000, 2), "km", file=sys.stderr)
    for r in rs:
        refs = collections.Counter()
        for u, v, w, L in r["edges"]:
            t = G.ways[w].get("tags", {}); refs[t.get("ref") or t.get("highway")] += L
        print("   ", round(r["len"] / 1000, 2), "km plateau", round(r["plateau"] / 1000, 1), "km", [(k, round(x / 1000, 1)) for k, x in refs.most_common(5)], file=sys.stderr)
    res[a + "-" + b] = [{"len": r["len"], "plateau": r["plateau"], "edges": [[u, v, w] for u, v, w, L in r["edges"]]} for r in rs]
json.dump({"snap": snap, "pairs": res}, open("plateau_out.json", "w"))
