"""Reconstruct Kumano Kodo courses that OSM maps only partially, by routing between documented
waypoints on the OSM trail/road network (named Kodo ways strongly preferred).
Writes kodo_routes.geojson with one feature per route (+ the official Iseji KML lines)."""
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

# ---- Iseji: Mie Prefecture 熊野古道伊勢路ナビ KML (official route lines)
ns = {"k": "http://www.opengis.net/kml/2.2"}
raw = open("kodo/out4utf8h_alpha128.kml", encoding="utf-8").read()
raw = re.sub(r'\s+xsi:schemaLocation="[^"]*"', "", raw)
root = ET.fromstring(raw)
lines = []
for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
    nm = pm.find("k:name", ns); nm = nm.text if nm is not None else ""
    for ls in pm.iter("{http://www.opengis.net/kml/2.2}LineString"):
        c = ls.find("k:coordinates", ns).text.split()
        pts = [tuple(map(float, p.split(",")[:2])) for p in c]
        if len(pts) > 1: lines.append((nm, LineString(pts)))
print("iseji lines", len(lines))
iseji = unary_union([l for n, l in lines])
feats.append({"type": "Feature", "properties": {"route": "iseji", "method": "Mie Prefecture Iseji Navi KML"}, "geometry": mapping(iseji)})
json.dump({"type": "FeatureCollection", "features": feats}, open("kodo_routes.geojson", "w"))
print("written")
