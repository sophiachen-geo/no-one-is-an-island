"""Union of all plateau alternatives between the three shrines -> corridor graph.
Junctions: nodes of degree >= 3 in the union (plus the three shrine endpoints). Each chain between junctions
is a corridor. Chains shorter than MINLEN between two junctions are merged into their neighbours' junction
(collapsing intersections that are a few metres apart)."""
import json, collections, sys
from route import Graph, hav, ekey
roads = json.load(open("roads.json")); G = Graph(roads)
d = json.load(open("plateau_out.json"))
snap = {k: int(v) for k, v in d["snap"].items()}
E = {}   # undirected edge key -> (u, v, w, L)
use = collections.Counter()
for pair, rs in d["pairs"].items():
    for r in rs:
        for u, v, w in r["edges"]:
            k = ekey(u, v)
            E[k] = (u, v, w, hav(G.xy[u], G.xy[v])); use[k] += 1
nb = collections.defaultdict(set)
for (a, b) in E: nb[a].add(b); nb[b].add(a)
junction = {n for n, s in nb.items() if len(s) != 2} | set(snap.values())
# walk chains
done = set(); chains = []
for j in junction:
    for n in nb[j]:
        if ekey(j, n) in done: continue
        chain = [j, n]; done.add(ekey(j, n))
        while chain[-1] not in junction:
            cur = chain[-1]; nxt = [x for x in nb[cur] if x != chain[-2]]
            if not nxt: break
            done.add(ekey(cur, nxt[0])); chain.append(nxt[0])
        chains.append(chain)
print("union edges", len(E), "junctions", len(junction), "chains", len(chains), file=sys.stderr)
L = lambda c: sum(hav(G.xy[a], G.xy[b]) for a, b in zip(c, c[1:]))
lens = sorted(L(c) for c in chains)
print("chain lengths: n<200m", sum(1 for x in lens if x < 200), "200-1000", sum(1 for x in lens if 200 <= x < 1000), ">=1000", sum(1 for x in lens if x >= 1000), "total km", round(sum(lens) / 1000, 1), file=sys.stderr)
json.dump({"chains": chains, "junction": list(junction), "snap": snap}, open("chains.json", "w"))
