"""Route families between the shrines on the chain graph: all simple paths up to STRETCH x the shortest, deduplicated
by the set of long chains (>= 2 km) they use, shortest member kept."""
import json, collections
C = {r["id"]: r for r in json.load(open("corridors.json"))}
CH = json.load(open("chains.json"))
SN = {k: int(v) for k, v in CH["snap"].items()}
adj = collections.defaultdict(list)
for cid, r in C.items():
    adj[r["a"]].append((r["b"], cid, +1)); adj[r["b"]].append((r["a"], cid, -1))
def options(a, b, stretch=1.6, cap=400):
    s, t = SN[a], SN[b]
    best = {}
    out = []
    import heapq
    # shortest for the cap
    dist = {s: 0}; pq = [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]: continue
        for v, cid, o in adj[u]:
            nd = d + C[cid]["len_m"]
            if nd < dist.get(v, 1e18): dist[v] = nd; heapq.heappush(pq, (nd, v))
    D = dist[t]
    def dfs(n, seen, acc, L):
        if len(out) > 20000 or L > stretch * D: return
        if n == t: out.append((L, list(acc))); return
        for v, cid, o in adj[n]:
            if v in seen: continue
            seen.add(v); acc.append((cid, o)); dfs(v, seen, acc, L + C[cid]["len_m"]); acc.pop(); seen.discard(v)
    dfs(s, {s}, [], 0)
    out.sort(key=lambda x: x[0])
    fam = {}
    for L, seq in out:
        sig = frozenset(cid for cid, o in seq if C[cid]["len_m"] >= 2000)
        if sig not in fam: fam[sig] = (L, seq)
    res = sorted(fam.values(), key=lambda x: x[0])
    return D, res
if __name__ == "__main__":
    for a, b in (("hongu", "hayatama"), ("hayatama", "nachi"), ("nachi", "hongu")):
        D, res = options(a, b)
        print(a, b, "shortest", round(D / 1000, 2), "families", len(res))
        for L, seq in res[:12]:
            up = sum((C[c]["up5"][0] if o > 0 else C[c]["up5"][1]) for c, o in seq)
            longs = [f"c{c}:{(C[c]['refs'][0][0] or C[c]['hw'] and max(C[c]['hw'], key=C[c]['hw'].get))}" for c, o in seq if C[c]["len_m"] >= 2000]
            print(f"   {L/1000:5.1f} km up {up:5d}  {' '.join(longs)}")
