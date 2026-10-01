"""Reconstruct Kumano Kodo courses that OSM maps only partially, by routing between documented
waypoints on the OSM trail/road network (named Kodo ways strongly preferred).
Writes kodo_routes.geojson with one feature per route: Omine Okugake, Ohechi (--ohechi) and Iseji.
Inputs: osm/trail_*.json and osm/route_*.json (fetch_osm.py --trails), osm/coast.json (fetch_osm.py)."""
import json, math, heapq, re, sys, xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import linemerge, unary_union
from pyproj import Transformer
TF = Transformer.from_crs(4326, 6674, always_xy=True).transform
INV = Transformer.from_crs(6674, 4326, always_xy=True).transform

def graph(files, weight):
    adj = {}
    for f in files:
        for el in json.load(open(f))["elements"]:
            if el["type"] != "way" or len(el.get("geometry", [])) < 2: continue
            w = weight(el.get("tags", {}))
            if w is None: continue
            pts = [TF(p["lon"], p["lat"]) for p in el["geometry"]]
            ks = [(round(x, 1), round(y, 1)) for x, y in pts]
            for a, b in zip(ks, ks[1:]):
                if a == b: continue
                d = math.hypot(b[0] - a[0], b[1] - a[1])
                adj.setdefault(a, []).append((b, d * w, d)); adj.setdefault(b, []).append((a, d * w, d))
    # keep only the largest connected component so every waypoint snaps onto one network
    seen, best = set(), []
    for k in adj:
        if k in seen: continue
        comp, stack = [], [k]; seen.add(k)
        while stack:
            u = stack.pop(); comp.append(u)
            for v, _, _ in adj[u]:
                if v not in seen: seen.add(v); stack.append(v)
        if len(comp) > len(best): best = comp
    keys = best; tree = cKDTree(np.array(keys))
    return adj, keys, tree

def route(adj, keys, tree, wps, snap_max=1500):
    out, gaps = [], []
    snapped = []
    for lon, lat in wps:
        x, y = TF(lon, lat); d, i = tree.query((x, y))
        snapped.append((keys[i], d))
    for (s, ds), (t, dt) in zip(snapped, snapped[1:]):
        dist = {s: 0.0}; prev = {}; pq = [(0.0, s)]
        while pq:
            c, u = heapq.heappop(pq)
            if u == t: break
            if c > dist.get(u, 1e18): continue
            for v, w, _ in adj[u]:
                nc = c + w
                if nc < dist.get(v, 1e18): dist[v] = nc; prev[v] = u; heapq.heappush(pq, (nc, v))
        if t not in prev and s != t:
            gaps.append((s, t)); out.append([s, t]); continue
        path = [t]
        while path[-1] != s: path.append(prev[path[-1]])
        path = path[::-1]
        plen = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(path, path[1:]))
        straight = math.hypot(t[0] - s[0], t[1] - s[1])
        if straight > 300 and plen > 2.5 * straight:       # the network detours: keep a straight, flagged leg
            gaps.append((s, t)); out.append([s, t]); continue
        out.append(path)
    coords = []
    for seg in out:
        for p in seg:
            if not coords or coords[-1] != p: coords.append(p)
    return LineString(coords), snapped, gaps

def okugake_weight(t):
    hw = t.get("highway"); nm = t.get("name", "")
    if "奥駈" in nm or "奥駆" in nm: return 0.25
    if hw in ("path", "footway", "steps", "bridleway"): return 1.0
    if hw == "track": return 1.8
    if hw in ("unclassified", "residential", "service", "tertiary", "secondary"): return 3.0
    return None

def ohechi_weight(t):
    hw = t.get("highway"); nm = t.get("name", "")
    if "熊野古道" in nm or "大辺路" in nm or nm in ("長井坂", "富田坂", "仏坂") or "仏坂" in nm: return 0.25
    if hw in ("path", "footway", "steps", "track"): return 1.0
    if hw in ("unclassified", "residential", "living_street", "service"): return 1.0
    if hw in ("tertiary", "secondary"): return 1.15
    if hw in ("primary", "trunk"): return 1.5
    return None

feats = []
# ---- Omine Okugake: Yoshino (Kinpusen-ji) -> ridge peaks -> Tamaki -> Hongu (Oyunohara)
peaks = {}
for e in json.load(open("osm/pois.json"))["elements"]:
    t = e.get("tags", {})
    if t.get("natural") == "peak" and t.get("name"):
        peaks.setdefault(t["name"], []).append((e.get("lon") or e["center"]["lon"], e.get("lat") or e["center"]["lat"]))
def pk(name, near=None):
    c = peaks[name]
    if near: c = sorted(c, key=lambda p: (p[0] - near[0]) ** 2 + (p[1] - near[1]) ** 2)
    return c[0]
OKU = [(135.8589, 34.3656), pk("青根ヶ峰"), pk("四寸岩山"), pk("大天井ヶ岳"), pk("山上ヶ岳"), pk("大普賢岳"), pk("国見岳"), pk("七曜岳"),
       pk("行者還岳"), pk("弁天の森"), pk("弥山"), pk("八経ヶ岳"), pk("明星ヶ岳"), pk("仏生嶽"), pk("孔雀岳"), pk("釈迦ヶ岳"),
       pk("大日岳", (135.905, 34.10)), pk("天狗山"), pk("地蔵岳", (135.90, 34.08)), pk("涅槃岳"), pk("転法輪岳"), pk("行仙岳", (135.905, 34.00)),
       pk("笠捨山"), pk("地蔵岳", (135.885, 33.987)), pk("玉置山", (135.83, 33.927)), pk("大森山", (135.805, 33.904)), (135.7707, 33.8408)]
adj, keys, tree = graph(["osm/trail_okugake.json", "osm/route_okugake.json"], okugake_weight)
oku, snapped, gaps = route(adj, keys, tree, OKU)
print("okugake km", round(oku.length / 1000, 1), "max snap m", round(max(d for _, d in snapped)), "gaps", [(INV(*a), INV(*b)) for a, b in gaps])
feats.append({"type": "Feature", "properties": {"route": "okugake", "method": "OSM network routed between ridge peaks"},
              "geometry": mapping(LineString([INV(x, y) for x, y in oku.coords]))})

# ---- Ohechi: Tanabe -> Tonda -> Hotokezaka -> Susami -> Nagaizaka -> coast -> Kushimoto -> Koza -> Uragami -> Hama-no-miya -> Nachi
if "--ohechi" in sys.argv:
    OHE = [(135.3845, 33.7329), (135.3934, 33.6527), (135.486, 33.6008), (135.4957, 33.5468), (135.57431, 33.52027), (135.5757, 33.5153),
           (135.6033, 33.5098), (135.655, 33.5011), (135.6779, 33.4903), (135.7187, 33.488), (135.7357, 33.4908), (135.7817, 33.4756),
           (135.8209, 33.5193), (135.8683, 33.5365), (135.8939, 33.5604), (135.9224, 33.5824), (135.9249, 33.6095), (135.9344, 33.6447),
           (135.8903, 33.6685)]
    adj, keys, tree = graph(["osm/trail_ohechi.json", "osm/route_ohechi.json"], ohechi_weight)
    ohe, snapped, gaps = route(adj, keys, tree, OHE)
    print("ohechi km", round(ohe.length / 1000, 1), "max snap m", round(max(d for _, d in snapped)), "gaps", [(INV(*a), INV(*b)) for a, b in gaps])
    feats.append({"type": "Feature", "properties": {"route": "ohechi", "method": "OSM network routed via Tonda, Hotokezaka, Nagaizaka and coastal stations"},
                  "geometry": mapping(LineString([INV(x, y) for x, y in ohe.coords]))})

# ---- Iseji: rebuilt on OSM paths between the passes and villages that GSI's base map names along the course, the
# 浜街道 along the OSM coastline of 七里御浜. Mie Prefecture's own route lines (熊野古道伊勢路ナビ) are All Rights Reserved
# and are not used; their section names fix the course: ツヅラト峠, 熊ヶ谷道 to 三浦峠, 始神峠, 馬越峠, 八鬼山, 三木峠,
# 羽後峠, 曽根次郎坂・太郎坂, 二木島峠・逢神坂峠, 波田須の道, 大吹峠, 観音道, 松本峠, 七里御浜, and the 本宮道 by
# 横垣峠, 風伝峠, 矢の川, 小栗栖, 板屋, 大河内 and 地薬 to the Kumano at 楊枝. (The later 荷坂峠 variant is not drawn: OSM
# maps no connected path down its south side.)
def graph_tied(files, weight, tie=20.0):
    """graph() plus ties: a way that ends within `tie` metres of another way is joined to it (OSM paths often stop
    short of the road they meet)."""
    adj, seen_ids = {}, set()
    for f in files:
        for el in json.load(open(f))["elements"]:
            if el["type"] != "way" or len(el.get("geometry", [])) < 2 or el["id"] in seen_ids: continue
            seen_ids.add(el["id"]); w = weight(el.get("tags", {}))
            if w is None: continue
            ks = [(round(x, 1), round(y, 1)) for x, y in (TF(p["lon"], p["lat"]) for p in el["geometry"])]
            for a, b in zip(ks, ks[1:]):
                if a == b: continue
                d = math.hypot(b[0] - a[0], b[1] - a[1])
                adj.setdefault(a, []).append((b, d * w, d)); adj.setdefault(b, []).append((a, d * w, d))
    keys = list(adj); tr = cKDTree(np.array(keys))
    for k in keys:
        if len(adj[k]) != 1: continue
        for jj in tr.query_ball_point(k, tie):
            q = keys[jj]
            if q == k or any(v == q for v, _, _ in adj[k]): continue
            d = math.hypot(q[0] - k[0], q[1] - k[1]); adj[k].append((q, d, d)); adj[q].append((k, d, d)); break
    seen, best = set(), []
    for k in adj:
        if k in seen: continue
        comp, stack = [], [k]; seen.add(k)
        while stack:
            u = stack.pop(); comp.append(u)
            for v, _, _ in adj[u]:
                if v not in seen: seen.add(v); stack.append(v)
        if len(comp) > len(best): best = comp
    return adj, best, cKDTree(np.array(best))

def iseji_weight(t):
    hw = t.get("highway"); nm = t.get("name", "")
    if "熊野古道" in nm or "伊勢路" in nm: return 0.3
    if hw in ("path", "footway", "steps", "bridleway"): return 0.8
    if hw == "track": return 1.0
    if hw in ("unclassified", "residential", "living_street", "service"): return 1.2
    if hw == "tertiary": return 1.5
    if hw == "secondary": return 1.8
    if hw in ("primary", "trunk"): return 2.6
    return None

# (lon, lat) of the names on GSI's base map (電子国土基本図 注記, experimental_anno z15) unless marked OSM
ISE = {"滝原宮": (136.4254, 34.36621), "大内山": (136.37396, 34.28645), "梅ヶ谷": (136.35817, 34.25505), "ツヅラト峠": (136.32866, 34.24566),
       "三浦": (136.28005, 34.17108), "船津": (136.21125, 34.12958), "馬越峠": (136.20179, 34.09378),
       "八鬼山登り口": (136.2051918, 34.0562533),                                    # OSM node 11934169583, 八鬼山登り口 (尾鷲市街側)
       "八鬼山": (136.21775, 34.03159), "三木里": (136.21152, 34.00152), "賀田": (136.18587, 33.97881), "甫母": (136.201, 33.94868),
       "二木島峠": (136.16971, 33.94126), "逢神坂峠": (136.16189, 33.94063), "大吹峠": (136.13161, 33.90497), "松本峠": (136.11155, 33.89768),
       "花の窟": (136.09341, 33.87978), "井田": (136.02447, 33.76514), "鵜殿": (136.0058, 33.73696), "有馬": (136.07982, 33.87712), "神木": (136.02627, 33.87119),
       "阪本": (135.99493, 33.86066), "風伝峠": (135.9655, 33.862), "矢ノ川": (135.94396, 33.86347), "小栗須": (135.9218, 33.87138),
       "板屋": (135.9117, 33.8791), "大河内": (135.90086, 33.84647), "楊枝川": (135.88735, 33.83015), "楊枝": (135.86401, 33.81796)}
ISE_MAIN = ["滝原宮", "大内山", "梅ヶ谷", "ツヅラト峠", "三浦", "船津", "馬越峠", "八鬼山登り口", "八鬼山", "三木里", "賀田", "甫母", "二木島峠",
            "逢神坂峠", "大吹峠", "松本峠", "花の窟"]
ISE_HONGU = ["花の窟", "有馬", "神木", "阪本", "風伝峠", "矢ノ川", "小栗須", "板屋", "大河内", "楊枝川", "楊枝"]
adj, keys, tree = graph_tied(["osm/trail_iseji.json"], iseji_weight)
ise_parts, ise_gaps = [], []
for leg in (ISE_MAIN, ISE_HONGU):
    ln, snapped, gaps = route(adj, keys, tree, [ISE[n] for n in leg])
    print("iseji", leg[0], "→", leg[-1], "km", round(ln.length / 1000, 1), "max snap m", round(max(d for _, d in snapped)), "gaps", len(gaps))
    ise_parts.append(ln); ise_gaps += gaps
# 浜街道: the OSM coastline from opposite 花の窟 to opposite 井田, then the network to the Kumano at 鵜殿
from shapely.geometry import Point
from shapely.ops import substring
coast = linemerge([LineString([TF(p["lon"], p["lat"]) for p in e["geometry"]]) for e in json.load(open("osm/coast.json"))["elements"]
                   if e["type"] == "way" and any(135.99 < p["lon"] < 136.11 and 33.72 < p["lat"] < 33.89 for p in e["geometry"])])
a, b = Point(TF(*ISE["花の窟"])), Point(TF(*ISE["井田"]))
cl = min(getattr(coast, "geoms", [coast]), key=lambda g: g.distance(a) + g.distance(Point(TF(*ISE["鵜殿"]))))
da, db = cl.project(a), cl.project(b)
beach = substring(cl, min(da, db), max(da, db))
print("iseji beach km", round(beach.length / 1000, 1), "ends", round(cl.distance(a)), round(cl.distance(b)), "m off the coast")
ise_parts.append(LineString([a.coords[0], beach.interpolate(da - min(da, db)).coords[0]]))     # 花の窟 to the shore
ise_parts.append(beach)
# off the beach at 井田 and through to the Kumano at 鵜殿, where the crossing was
south = beach.interpolate(db - min(da, db)).coords[0]
ln, snapped, gaps = route(adj, keys, tree, [INV(*south), ISE["鵜殿"]])
print("iseji 井田 → 鵜殿 km", round(ln.length / 1000, 1), "gaps", len(gaps)); ise_parts.append(ln); ise_gaps += gaps
iseji = MultiLineString([[INV(x, y) for x, y in l.coords] for l in ise_parts])
feats.append({"type": "Feature", "properties": {"route": "iseji", "method": "OSM network routed between the passes and villages named on GSI's base map; 浜街道 along the OSM coastline",
              "gaps": len(ise_gaps)}, "geometry": mapping(iseji)})
if "--check-mie" in sys.argv:     # optional: compare with a local copy of Mie Prefecture's route data (not redistributed)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    raw = re.sub(r'\s+xsi:schemaLocation="[^"]*"', "", open("kodo/out4utf8h_alpha128.kml", encoding="utf-8").read())
    K = unary_union([LineString([TF(*map(float, c.split(",")[:2])) for c in ls.find("k:coordinates", ns).text.split()])
                     for ls in ET.fromstring(raw).iter("{http://www.opengis.net/kml/2.2}LineString")])
    d = np.array([K.distance(l.interpolate(x)) for l in ise_parts for x in np.arange(0, l.length, 50)])
    print(f"iseji vs Mie: median {np.median(d):.0f} m, within 100 m {100 * np.mean(d <= 100):.0f}%, within 500 m {100 * np.mean(d <= 500):.0f}%, max {d.max():.0f} m")
json.dump({"type": "FeatureCollection", "features": feats}, open("kodo_routes.geojson", "w"))
print("written")
