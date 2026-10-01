"""Shingū town core: width conflation, three movement networks (walk / bike / car), route directness, and the
photo-dated ride of 28 Sep 2025 coded every 20 m. Metric work in JGD2011 / CS VI (EPSG:6674)."""
import json, math, sys, collections, heapq, random, os
import numpy as np
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from pyproj import Transformer
import town_gsi
from route import legal, hav
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
INV = Transformer.from_crs(6674, 4326, always_xy=True).transform
TB = (135.972, 33.712, 136.004, 33.736)           # analysis frame
CORE = (135.976, 33.716, 136.001, 33.734)         # where directness is reported
H = os.getcwd()
roads = json.load(open(os.path.join(H, "roads.json")))
G = town_gsi.layers()
# ---------------- 1. width conflation: GSI RdCL (vt_rdctg, vt_rnkwidth) onto OSM ways -----------------
rd = [(g, p) for g, p in G["RdCL"]]
rtree = STRtree([g for g, p in rd])
def bearing(a, b): return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 180
def gsi_at(x, y, brg, tol=7.0):
    best = None
    for i in rtree.query(Point(x, y).buffer(tol)):
        g, p = rd[i]
        d = g.distance(Point(x, y))
        if d > tol: continue
        s = g.project(Point(x, y)); a = g.interpolate(max(0, s - 2)); b = g.interpolate(min(g.length, s + 2))
        db = abs(bearing((a.x, a.y), (b.x, b.y)) - brg); db = min(db, 180 - db)
        if db > 30: continue
        if best is None or d < best[0]: best = (d, p.get("vt_rnkwidth"), p.get("vt_rdctg"))
    return best
ways = {}
for e in roads["elements"]:
    g = e.get("geometry") or []
    if not g or not any(TB[0] <= q["lon"] <= TB[2] and TB[1] <= q["lat"] <= TB[3] for q in g): continue
    ways[e["id"]] = e
wclass = {}; wstats = collections.Counter()
for wid, e in ways.items():
    xy = [TR(q["lon"], q["lat"]) for q in e["geometry"]]
    votes = collections.Counter(); L = 0.0
    for a, b in zip(xy, xy[1:]):
        seg = math.dist(a, b); L += seg; n = max(1, int(seg // 5))
        brg = bearing(a, b)
        for k in range(n):
            f = (k + 0.5) / n; x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            r = gsi_at(x, y, brg)
            votes[(r[1], r[2]) if r else (None, None)] += seg / n
    top = votes.most_common(1)[0][0] if votes else (None, None)
    matched = sum(v for k, v in votes.items() if k[0]) / max(L, 1e-9)
    wclass[wid] = {"w": top[0] if matched >= 0.5 else None, "ctg": top[1] if matched >= 0.5 else None, "match": round(matched, 2)}
    wstats[(e.get("tags", {}).get("highway"), wclass[wid]["w"])] += L
print("conflation (km by OSM class x GSI width):", file=sys.stderr)
for k, v in sorted(wstats.items(), key=lambda kv: -kv[1])[:24]: print("  ", k, round(v / 1000, 2), file=sys.stderr)
# ---------------- 2. three networks -----------------
WALK_NO = {"motorway", "motorway_link", "construction", "proposed", "bus_guideway", "raceway"}
CAR_OK = {"trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service"}
def mode_ok(mode, t, wc):
    hw = t.get("highway")
    if t.get("access") in ("no", "private") and not t.get(mode_key(mode)) in ("yes", "designated", "permissive"): return False
    if mode == "walk":
        return hw not in WALK_NO and t.get("foot") != "no" and t.get("area") != "yes"
    if mode == "bike":
        return legal(t)[0]
    if mode == "car":
        if hw not in CAR_OK or t.get("motor_vehicle") == "no" or t.get("motorcar") == "no": return False
        if hw == "service" and t.get("service") in ("parking_aisle", "drive-through"): return False
        return wc.get("w") != "3m未満"           # lanes under 3 m (GSI) treated as not passable for through car traffic
def mode_key(mode): return {"walk": "foot", "bike": "bicycle", "car": "motor_vehicle"}[mode]
def oneway(mode, t):
    if mode == "walk": return 0
    o = (t.get("oneway:bicycle") if mode == "bike" else None) or t.get("oneway")
    if t.get("junction") == "roundabout": o = o or "yes"
    return {"yes": 1, "true": 1, "1": 1, "-1": -1}.get(o, 0)
NODES = {}
def build(mode):
    adj = collections.defaultdict(list)
    for wid, e in ways.items():
        t = e.get("tags", {})
        if not mode_ok(mode, t, wclass[wid]): continue
        ow = oneway(mode, t)
        ns = e["nodes"]; gs = e["geometry"]
        for i in range(len(ns) - 1):
            a, b = ns[i], ns[i + 1]
            pa, pb = TR(gs[i]["lon"], gs[i]["lat"]), TR(gs[i + 1]["lon"], gs[i + 1]["lat"])
            NODES[a], NODES[b] = pa, pb
            L = math.dist(pa, pb)
            if ow >= 0: adj[a].append((b, L, wid))
            if ow <= 0: adj[b].append((a, L, wid))
    return adj
NET = {m: build(m) for m in ("walk", "bike", "car")}
for m, adj in NET.items(): print(m, "nodes", len(adj), "edges", sum(len(v) for v in adj.values()), file=sys.stderr)
def dijkstra(adj, s, limit=None):
    dist = {s: 0.0}; pq = [(0.0, s)]; prev = {}
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]: continue
        if limit and d > limit: break
        for v, L, w in adj.get(u, ()):
            nd = d + L
            if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = (u, w); heapq.heappush(pq, (nd, v))
    return dist, prev
def reverse(adj):
    r = collections.defaultdict(list)
    for u, lst in adj.items():
        for v, L, w in lst: r[v].append((u, L, w))
    return r
# ---------------- 3. route directness from every building, by mode -----------------
from shapely.strtree import STRtree as _T
bld = {}
for g, p in G["BldA"]:
    c = g.representative_point(); lon, lat = INV(c.x, c.y)
    if not (CORE[0] <= lon <= CORE[2] and CORE[1] <= lat <= CORE[3]): continue
    k = (round(c.x, 0), round(c.y, 0))
    if any((k[0] + dx, k[1] + dy) in bld for dx in (-1, 0, 1) for dy in (-1, 0, 1)): continue   # tile-buffer duplicates
    bld[k] = (c.x, c.y, g.area)
B = list(bld.values())
print("buildings in core", len(B), file=sys.stderr)
def snapper(adj):
    ids = [n for n in adj if n in NODES]
    arr = np.array([NODES[n] for n in ids])
    from scipy.spatial import cKDTree
    return ids, cKDTree(arr)
ACC_MAX = 60.0
random.seed(20250928)
dest_idx = random.sample(range(len(B)), min(260, len(B)))
DIR = {}; NOACC = {}
for mode, adj in NET.items():
    ids, kd = snapper(adj)
    d_acc, j = kd.query(np.array([(b[0], b[1]) for b in B]))
    snapn = [ids[k] for k in j]
    radj = reverse(adj)
    vals = [[] for _ in B]
    for di in dest_idx:
        if d_acc[di] > ACC_MAX: continue
        dist, _ = dijkstra(radj, snapn[di], limit=4000)       # network distance from every node to this destination
        bx, by = B[di][0], B[di][1]
        for oi, b in enumerate(B):
            if oi == di or d_acc[oi] > ACC_MAX: continue
            e = math.hypot(b[0] - bx, b[1] - by)
            if not (150 <= e <= 800): continue
            nd = dist.get(snapn[oi])
            if nd is None: continue
            vals[oi].append((d_acc[oi] + nd + d_acc[di]) / e)
    DIR[mode] = [float(np.median(v)) if len(v) >= 8 else (None if d_acc[i] > ACC_MAX else -1.0) for i, v in enumerate(vals)]
    NOACC[mode] = int((d_acc > ACC_MAX).sum())
    ok = [x for x in DIR[mode] if x is not None and x > 0]
    print(mode, "buildings scored", len(ok), "median directness", round(float(np.median(ok)), 3), "IQR", [round(float(q), 3) for q in np.percentile(ok, [25, 75])], "no access (>60 m)", int((d_acc > ACC_MAX).sum()), file=sys.stderr)
# ---------------- 4. the ride of 28 Sep 2025, from the photographs -----------------
import dem
PH = json.load(open(os.path.join(H, "..", "photos", "manifest.json")))
PH = sorted([p for p in PH if p.get("lat")], key=lambda p: p["time"])
for p in PH: p["xy"] = TR(p["lon"], p["lat"])
sites = []
for p in PH:
    if sites and math.dist(sites[-1][-1]["xy"], p["xy"]) <= 150: sites[-1].append(p)
    else: sites.append([p])
print("sites", [(s[0]["file"], s[-1]["file"], s[0]["time"][11:16], s[-1]["time"][11:16]) for s in sites], file=sys.stderr)
bike = NET["bike"]; bids, bkd = snapper(bike)
def snap_b(xy):
    d, k = bkd.query(xy); return bids[k], d
POI = json.load(open(os.path.join(H, "town", "osm_pois.json")))["elements"]
def poi_xy(e):
    if e["type"] == "node": return TR(e["lon"], e["lat"])
    g = e.get("geometry") or []
    if not g: return None
    xs = [TR(q["lon"], q["lat"]) for q in g]; return (sum(x for x, y in xs) / len(xs), sum(y for x, y in xs) / len(xs))
COMM = {"restaurant", "cafe", "fast_food", "bar", "pub", "bank", "pharmacy", "post_office", "ice_cream", "marketplace", "fuel"}
shops = [poi_xy(e) for e in POI if (e.get("tags", {}).get("shop") or e.get("tags", {}).get("amenity") in COMM) and poi_xy(e)]
from shapely.geometry import Polygon as _P
def poly_of(e):
    g = e.get("geometry") or []
    if len(g) < 4 or g[0] != g[-1]: return None
    try: return _P([TR(q["lon"], q["lat"]) for q in g]).buffer(0)
    except Exception: return None
sacred = [poly_of(e) for e in POI if e["type"] == "way" and (e.get("tags", {}).get("landuse") == "religious" or e.get("tags", {}).get("amenity") == "place_of_worship")]
sacred = [g for g in sacred if g is not None and not g.is_empty]
sacred_pts = [poi_xy(e) for e in POI if e["type"] == "node" and e.get("tags", {}).get("amenity") == "place_of_worship"]
trees = [poly_of(e) for e in POI if e["type"] == "way" and (e.get("tags", {}).get("natural") in ("wood",) or e.get("tags", {}).get("leisure") == "park")]
trees = [g for g in trees if g is not None and not g.is_empty]
tree_pts = [poi_xy(e) for e in POI if e["type"] == "node" and e.get("tags", {}).get("natural") == "tree"]
water = [g for g, p in G["WA"]] + [g for g, p in G["WL"]]
bldg = [g for g, p in G["BldA"]]
T_s, T_w, T_b, T_t = STRtree(sacred) if sacred else None, STRtree(water), STRtree(bldg), STRtree(trees) if trees else None
from scipy.spatial import cKDTree
K_shop = cKDTree(np.array(shops)) if shops else None
K_sp = cKDTree(np.array(sacred_pts)) if sacred_pts else None
K_tp = cKDTree(np.array(tree_pts)) if tree_pts else None
def near(tree, geoms, x, y, r):
    if tree is None: return False
    P = Point(x, y)
    return any(geoms[i].distance(P) <= r for i in tree.query(P.buffer(r)))
legs = []
for i in range(len(sites) - 1):
    a, b = sites[i][-1], sites[i + 1][0]
    sa, da = snap_b(a["xy"]); sb, db = snap_b(b["xy"])
    dist, prev = dijkstra(bike, sa)
    if sb not in dist: print("no bike path", a["file"], b["file"], file=sys.stderr); continue
    path = [sb]; wids = []
    while path[-1] != sa:
        u, w = prev[path[-1]]; wids.append(w); path.append(u)
    path = path[::-1]; wids = wids[::-1]
    xy = [NODES[n] for n in path]
    # sample every 20 m
    line = LineString(xy); L = line.length; n = max(2, int(L // 20) + 1)
    seg_w = []   # way id per sample
    cum = [0.0]
    for p, q in zip(xy, xy[1:]): cum.append(cum[-1] + math.dist(p, q))
    rows = []; wid_at = []
    for k in range(n):
        s = min(L, k * 20.0); P = line.interpolate(s)
        j = max(0, min(len(wids) - 1, int(np.searchsorted(cum, s, side="right")) - 1))
        wid = wids[j]; wid_at.append(wid); t = ways[wid].get("tags", {}); wc = wclass[wid]
        lon, lat = INV(P.x, P.y); h, src = dem.sample(lon, lat)
        # frontage: points 6-10 m either side, every 4 m along, inside a building footprint
        P0 = line.interpolate(max(0, s - 10)); P1 = line.interpolate(min(L, s + 10))
        dx, dy = P1.x - P0.x, P1.y - P0.y; Ln = math.hypot(dx, dy) or 1; nx, ny = -dy / Ln, dx / Ln
        hits = tot = 0
        for along in (-8, -4, 0, 4, 8):
            for side in (-1, 1):
                for off in (6, 9):
                    qx = P.x + dx / Ln * along + side * nx * off; qy = P.y + dy / Ln * along + side * ny * off
                    tot += 1
                    if any(bldg[ii].contains(Point(qx, qy)) for ii in T_b.query(Point(qx, qy))): hits += 1
        rows.append({"s": round(s, 1), "lon": round(lon, 6), "lat": round(lat, 6), "h": round(h, 1) if h is not None else None,
                     "w": wc["w"], "ctg": wc["ctg"], "hw": t.get("highway"), "ref": t.get("ref"), "name": t.get("name"), "surf": t.get("surface"),
                     "shops": int(len(K_shop.query_ball_point((P.x, P.y), 25))) if K_shop is not None else 0,
                     "sacred": bool(near(T_s, sacred, P.x, P.y, 30) or (K_sp is not None and len(K_sp.query_ball_point((P.x, P.y), 30)) > 0)),
                     "water": bool(near(T_w, water, P.x, P.y, 25)),
                     "trees": bool(near(T_t, trees, P.x, P.y, 12) or (K_tp is not None and len(K_tp.query_ball_point((P.x, P.y), 12)) > 0)),
                     "front": round(hits / tot, 2)})
    # bridges and tunnels: the DEM is the ground under the deck (or over the bore), so interpolate between their ends
    st = [bool(ways[wid_at[k]].get("tags", {}).get("bridge") not in (None, "no") or ways[wid_at[k]].get("tags", {}).get("tunnel") not in (None, "no")) for k in range(len(rows))]
    k = 0
    while k < len(rows):
        if st[k]:
            j = k
            while j < len(rows) and st[j]: j += 1
            ia, ib = k - 1, j if j < len(rows) else None
            for q in range(k, j):
                if ia >= 0 and ib is not None and rows[ia]["h"] is not None and rows[ib]["h"] is not None:
                    f = (rows[q]["s"] - rows[ia]["s"]) / (rows[ib]["s"] - rows[ia]["s"]); rows[q]["h"] = round(rows[ia]["h"] + (rows[ib]["h"] - rows[ia]["h"]) * f, 1)
                rows[q]["struct"] = 1
            k = j
        else: k += 1
    hs = [r["h"] for r in rows if r["h"] is not None]
    legs.append({"from": a["file"], "to": b["file"], "t0": a["time"], "t1": b["time"], "len_m": round(L), "snap_m": [round(da, 1), round(db, 1)],
                 "xy": [[round(x, 1), round(y, 1)] for x, y in xy], "rows": rows,
                 "up": round(sum(max(0, q - p) for p, q in zip(hs, hs[1:]) if abs(q - p) >= 0.5), 1)})
    print("leg", a["file"], "->", b["file"], a["time"][11:16], "->", b["time"][11:16], "route", round(L), "m snap", round(da, 1), round(db, 1), file=sys.stderr)
json.dump({"wclass": {str(k): v for k, v in wclass.items()}, "B": [[round(b[0], 1), round(b[1], 1)] for b in B],
           "dir": {m: [None if v is None else round(v, 3) for v in DIR[m]] for m in DIR}, "noacc": NOACC, "sites": [[p["file"] for p in s] for s in sites], "legs": legs},
          open(os.path.join(H, "town", "town_out.json"), "w"), ensure_ascii=False)
print("written town_out.json", file=sys.stderr)
