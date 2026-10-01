"""GSI optimal vector tiles (z16 RdCL) along every corridor -> road category and width class per corridor."""
import json, math, os, sys, time, urllib.request, collections
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from pyproj import Transformer
import mapbox_vector_tile
from route import Graph
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
D = os.path.join(os.getcwd(), "obv16_region"); os.makedirs(D, exist_ok=True)
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
def tile(lon, lat, z=16):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("corridors.json"))
need = set()
for r in C:
    for n in r["nodes"][::3] + [r["nodes"][-1]]:
        need.add(tile(*G.xy[n]))
print("tiles", len(need), file=sys.stderr)
for tx, ty in sorted(need):
    f = os.path.join(D, f"16_{tx}_{ty}.pbf")
    if os.path.exists(f): continue
    for a in range(5):
        try:
            b = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/16/{tx}/{ty}.pbf", headers=UA), timeout=60).read()
            open(f, "wb").write(b); break
        except urllib.error.HTTPError as e:
            if e.code == 404: open(f, "wb").close(); break
            time.sleep(2 + 2 * a)
        except Exception: time.sleep(2 + 2 * a)
def ll(tx, ty, ext, x, y, z=16):
    n = 2 ** z; X = (tx + x / ext) / n; Y = (ty + y / ext) / n
    return X * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y))))
lines = []
for tx, ty in sorted(need):
    f = os.path.join(D, f"16_{tx}_{ty}.pbf")
    if not os.path.getsize(f): continue
    t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
    L = t.get("RdCL")
    if not L: continue
    for ft in L["features"]:
        g = ft["geometry"]; cs = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        for c in cs:
            if len(c) < 2: continue
            lines.append((LineString([TR(*ll(tx, ty, L["extent"], x, y)) for x, y in c]), ft["properties"]))
tree = STRtree([g for g, p in lines])
def brg(a, b): return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 180
for r in C:
    xy = [TR(*G.xy[n]) for n in r["nodes"]]
    votes = collections.Counter(); tot = 0.0
    for a, b in zip(xy, xy[1:]):
        seg = math.dist(a, b); k = max(1, int(seg // 20)); bb = brg(a, b)
        for i in range(k):
            f = (i + 0.5) / k; P = Point(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            best = None
            for j in tree.query(P.buffer(12)):
                g, p = lines[j]; d = g.distance(P)
                if d > 12: continue
                s = g.project(P); q0 = g.interpolate(max(0, s - 3)); q1 = g.interpolate(min(g.length, s + 3))
                db = abs(brg((q0.x, q0.y), (q1.x, q1.y)) - bb); db = min(db, 180 - db)
                if db > 35: continue
                if best is None or d < best[0]: best = (d, p.get("vt_rdctg"), p.get("vt_rnkwidth"), p.get("vt_code"))
            votes[(best[1], best[2]) if best else ("(no GSI match)", None)] += seg / k
        tot += seg
    r["gsi"] = [[k[0], k[1], round(v)] for k, v in votes.most_common()]
    if r["len_m"] > 2000:
        print(r["id"], r["len_m"], [(k, round(v / max(tot, 1) * 100)) for k, v in votes.most_common(3)], file=sys.stderr)
json.dump(C, open("corridors.json", "w"), ensure_ascii=False)
