import json, collections, itertools, sys
from route import Graph, hav
C = json.load(open("corridors.json"))
CH = json.load(open("chains.json")); SN = {int(v): k for k, v in CH["snap"].items()}
roads = json.load(open("roads.json")); G = Graph(roads)
par = {}
def f(x):
    while par.get(x, x) != x: x = par[x]
    return x
def u(a, b):
    a, b = f(a), f(b)
    if a == b: return
    if b in SN: a, b = b, a          # shrine stays the representative
    par[b] = a
for r in C:
    if r["len_m"] < 400 and not (r["a"] in SN and r["b"] in SN):
        u(r["a"], r["b"])
edges = collections.defaultdict(list)
for r in C:
    a, b = f(r["a"]), f(r["b"])
    if a == b: continue
    edges[tuple(sorted((a, b)))].append(r)
# collapse parallel near-identical chains (dual carriageways)
E = []
for k, rs in edges.items():
    rs = sorted(rs, key=lambda r: r["len_m"]); keep = []
    for r in rs:
        if any(abs(r["len_m"] - q["len_m"]) < 0.1 * q["len_m"] and r["refs"][0][0] == q["refs"][0][0] for q in keep):
            continue
        keep.append(r)
    for r in keep: E.append((k[0], k[1], r))
nodes = sorted({n for a, b, r in E for n in (a, b)})
def nm(n):
    if n in SN: return SN[n]
    for r in C:
        if f(r["a"]) == n: return r["a_name"][0] if isinstance(r["a_name"], list) else r["a_name"]
        if f(r["b"]) == n: return r["b_name"][0] if isinstance(r["b_name"], list) else r["b_name"]
NAMES = {n: nm(n) for n in nodes}
print("nodes", len(nodes), "edges", len(E), file=sys.stderr)
for a, b, r in sorted(E, key=lambda e: -e[2]["len_m"]):
    print(f"  c{r['id']:2d} {NAMES[a]} — {NAMES[b]}  {r['len_m']/1000:.1f} km  refs {[x[0] for x in r['refs'][:3]]}", file=sys.stderr)
# route options between shrines: all simple paths with length <= 1.6 x shortest
adj = collections.defaultdict(list)
for a, b, r in E: adj[a].append((b, r)); adj[b].append((a, r))
S = {v: k for k, v in SN.items()}
def paths(s, t, cap):
    out = []
    def dfs(n, seen, acc, L):
        if L > cap: return
        if n == t: out.append((L, list(acc))); return
        for m, r in adj[n]:
            if m in seen: continue
            seen.add(m); acc.append(r); dfs(m, seen, acc, L + r["len_m"]); acc.pop(); seen.discard(m)
    dfs(s, {s}, [], 0)
    return sorted(out, key=lambda x: x[0])
res = {}
for a, b in [("hongu", "hayatama"), ("hayatama", "nachi"), ("nachi", "hongu")]:
    s, t = f(S[a]), f(S[b])
    allp = paths(s, t, 1e9 if False else 200000)
    sh = allp[0][0]
    keep = [p for p in allp if p[0] <= 1.6 * sh]
    print(a, b, "shortest", round(sh / 1000, 2), "options <=1.6x:", len(keep), file=sys.stderr)
    for L, rs in keep:
        up = sum(r["up5"][0] for r in rs)
        print(f"    {L/1000:5.1f} km  ~climb {up:4d} m  via " + " / ".join(f"c{r['id']}" for r in rs), file=sys.stderr)
    res[a + "-" + b] = [{"len_m": L, "chains": [r["id"] for r in rs]} for L, rs in keep]
json.dump({"names": {str(k): v for k, v in NAMES.items()}, "edges": [[a, b, r["id"]] for a, b, r in E], "options": res, "rep": {str(k): f(k) for k in set(x for r in C for x in (r["a"], r["b"]))}}, open("present.json", "w"), ensure_ascii=False)
