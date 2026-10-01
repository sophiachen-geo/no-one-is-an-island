"""Bike-legal routing between the three Kumano shrines on the OSM road network.

Legality (道路交通法): bicycles are 軽車両 and may use every road except 高速自動車国道 (motorway) and
自動車専用道路 (motorroad=yes), and any way signed against them (bicycle=no). Footways, paths and steps are
excluded unless OSM marks bicycles allowed; tracks (forest roads) are kept but flagged unpaved unless tagged.
Ferries are excluded.

Alternatives: iterative penalty — find the shortest path, multiply the cost of its edges by PEN, repeat; keep a
candidate if it is no longer than STRETCH x the shortest and shares at most OVERLAP of its length with every
route already kept (measured on the shorter of the two)."""
import json, math, heapq, sys, collections
R = 6371008.8
def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))
EXCL_HW = {"motorway", "motorway_link", "steps", "proposed", "construction", "bus_guideway", "escape", "raceway"}
FOOT = {"footway", "path", "pedestrian", "bridleway", "corridor"}
def legal(t):
    hw = t.get("highway")
    if hw in EXCL_HW: return False, "excluded class"
    if t.get("motorroad") == "yes": return False, "motorroad"
    if t.get("bicycle") in ("no", "use_sidepath", "dismount") and hw not in FOOT: return False, "bicycle=" + t.get("bicycle")
    if t.get("access") in ("no", "private") and t.get("bicycle") not in ("yes", "designated", "permissive"): return False, "access"
    if hw in FOOT and t.get("bicycle") not in ("yes", "designated", "permissive"): return False, "foot only"
    if t.get("route") == "ferry": return False, "ferry"
    if t.get("area") == "yes": return False, "area"
    return True, ""
def oneway(t):
    o = t.get("oneway:bicycle") or t.get("oneway")
    if t.get("highway") in ("motorway",) or t.get("junction") == "roundabout":
        o = o or "yes"
    return {"yes": 1, "true": 1, "1": 1, "-1": -1}.get(o, 0)
class Graph:
    def __init__(self, roads):
        self.ways = {}
        self.adj = collections.defaultdict(list)    # node -> [(nbr, length, wayid, i)]
        self.xy = {}
        self.rejected = collections.Counter()
        for e in roads["elements"]:
            if e["type"] != "way": continue
            t = e.get("tags", {})
            ok, why = legal(t)
            if not ok:
                self.rejected[why] += 1; continue
            ns, gs = e["nodes"], e["geometry"]
            self.ways[e["id"]] = e
            ow = oneway(t)
            for i in range(len(ns) - 1):
                a, b = ns[i], ns[i + 1]
                pa, pb = (gs[i]["lon"], gs[i]["lat"]), (gs[i + 1]["lon"], gs[i + 1]["lat"])
                self.xy[a], self.xy[b] = pa, pb
                L = hav(pa, pb)
                if ow >= 0: self.adj[a].append((b, L, e["id"], i))
                if ow <= 0: self.adj[b].append((a, L, e["id"], i))
    def nearest(self, lon, lat, pred=None):
        best = None
        for n, p in self.xy.items():
            if pred and not pred(n): continue
            d = hav(p, (lon, lat))
            if best is None or d < best[0]: best = (d, n)
        return best
    def dijkstra(self, s, t, cost):
        dist = {s: 0.0}; prev = {}
        pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t: break
            if d > dist.get(u, 1e18): continue
            for v, L, w, i in self.adj[u]:
                nd = d + cost(u, v, L, w)
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = (u, w, L); heapq.heappush(pq, (nd, v))
        if t not in dist: return None
        path = [t]; edges = []
        while path[-1] != s:
            u, w, L = prev[path[-1]]
            edges.append((u, path[-1], w, L)); path.append(u)
        return path[::-1], edges[::-1]
def length(edges): return sum(e[3] for e in edges)
def ekey(u, v): return (u, v) if u < v else (v, u)
def shared(e1, e2):
    s2 = {ekey(u, v) for u, v, w, L in e2}
    return sum(L for u, v, w, L in e1 if ekey(u, v) in s2)
def alternatives(G, s, t, PEN=4.0, STRETCH=1.6, OVERLAP=0.5, ITER=40):
    pen = collections.defaultdict(lambda: 1.0)
    kept = []
    base = None
    for it in range(ITER):
        r = G.dijkstra(s, t, lambda u, v, L, w: L * pen[ekey(u, v)])
        if r is None: break
        path, edges = r
        Lr = length(edges)
        if base is None: base = Lr
        for u, v, w, L in edges: pen[ekey(u, v)] *= PEN
        if Lr > STRETCH * base: continue
        ok = all(shared(edges, k[1]) <= OVERLAP * min(Lr, length(k[1])) for k in kept)
        if ok: kept.append((path, edges))
    return kept, base
