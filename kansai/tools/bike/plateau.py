"""Alternative routes by the plateau method (choice routing; Cambridge Vehicle Information Technology 2005,
Bader et al. 2011): build the forward shortest-path tree from A and the backward tree to B. Edges that lie
on both trees form 'plateaus'; each plateau x..y defines the route A->x (tree), x..y, y->B (tree), which
is a concatenation of shortest paths and therefore locally optimal. Long plateaus are natural alternatives."""
import heapq, collections
from route import ekey
def tree(adj, s):
    dist = {s: 0.0}; pred = {}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]: continue
        for v, L, w, i in adj[u]:
            nd = d + L
            if nd < dist.get(v, 1e18):
                dist[v] = nd; pred[v] = (u, w, L); heapq.heappush(pq, (nd, v))
    return dist, pred
def reverse(adj):
    r = collections.defaultdict(list)
    for u, lst in adj.items():
        for v, L, w, i in lst: r[v].append((u, L, w, i))
    return r
def path_from_tree(pred, s, t):
    """edges s->t following forward pred (pred[v] = (u, w, L))"""
    out = []; v = t
    while v != s:
        u, w, L = pred[v]; out.append((u, v, w, L)); v = u
    return out[::-1]
def path_to_target(succ, s, t):
    """edges s->t following backward tree (succ[u] = (v, w, L) meaning u->v toward t)"""
    out = []; u = s
    while u != t:
        v, w, L = succ[u]; out.append((u, v, w, L)); u = v
    return out
def plateaus(G, a, b, S=1.5, MINP=0.08, MAXSHARE=0.8, K=8):
    df, pf = tree(G.adj, a)
    db, pb = tree(reverse(G.adj), b)          # pb[u] = (v, w, L): u -> v is the next step toward b
    D = df[b]
    on = {}
    for v, (u, w, L) in pf.items():           # forward tree edge u->v
        q = pb.get(u)
        if q and q[0] == v: on[u] = (v, w, L)  # also backward tree edge u->v
    # chain plateau edges
    starts = set(on) - {v for v, *_ in on.values()}
    seen = set(); cand = []
    for s in list(starts) + list(on):
        if s in seen or s not in on: continue
        if s not in starts and any(True for _ in []): pass
        chain = []; u = s
        while u in on and u not in seen:
            seen.add(u); v, w, L = on[u]; chain.append((u, v, w, L)); u = v
        if not chain: continue
        x, y = chain[0][0], chain[-1][1]
        plen = sum(e[3] for e in chain)
        total = df[x] + plen + db[y]
        cand.append((plen, total, x, y, chain))
    cand.sort(key=lambda c: -c[0])
    routes = []
    for plen, total, x, y, chain in cand:
        if total > S * D or plen < MINP * D: continue
        edges = path_from_tree(pf, a, x) + chain + path_to_target(pb, y, b)
        Lr = sum(e[3] for e in edges)
        ks = {ekey(u, v) for u, v, w, L in edges}
        ok = True
        for r in routes:
            sh = sum(L for u, v, w, L in r["edges"] if ekey(u, v) in ks)
            if sh > MAXSHARE * min(Lr, r["len"]): ok = False; break
        if ok:
            routes.append({"edges": edges, "len": Lr, "plateau": plen, "x": x, "y": y})
        if len(routes) >= K: break
    return routes, D
