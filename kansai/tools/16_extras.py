"""Add the second-round layers to geo.json: precise/rebuilt Kumano Kodo, tsunami walking-distance bands,
landslide-exposed roads, timber flows + sea lanes, Ichida river/flood, old-town micro-relief, extra points."""
import json, os
from shapely.geometry import shape, mapping, LineString, MultiLineString, Polygon, MultiPolygon, Point
from shapely.ops import transform, unary_union, linemerge
from pyproj import Transformer
TF = Transformer.from_crs(6668, 6674, always_xy=True).transform
g = json.load(open("geo.json"))
x, y = TF(135.9925, 33.7241); px, py = g["pts"]["shingu"]; X0 = x - px * 100; Y1 = y + py * 100
def sx(X): return (X - X0) / 100.0
def sy(Y): return (Y1 - Y) / 100.0
def fnum(v):
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    if s.startswith("0."): s = s[1:]
    elif s.startswith("-0."): s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s
def ring_d(coords, prec, close):
    k = 10 ** prec; pts = []
    for X, Y in coords:
        q = (round(sx(X) * k), round(sy(Y) * k))
        if not pts or q != pts[-1]: pts.append(q)
    if close and len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
    if len(pts) < 2: return ""
    s = "M" + fnum(pts[0][0] / k) + " " + fnum(pts[0][1] / k) + "l"
    s += " ".join(fnum((b[0] - a[0]) / k) + ("" if fnum((b[1] - a[1]) / k).startswith("-") else " ") + fnum((b[1] - a[1]) / k) for a, b in zip(pts, pts[1:]))
    return s.replace(" -", "-") + ("z" if close else "")
def to_d(geom, prec=1):
    if geom is None or geom.is_empty: return ""
    if isinstance(geom, Polygon): return "".join(ring_d(r.coords, prec, True) for r in [geom.exterior, *geom.interiors])
    if isinstance(geom, LineString): return ring_d(geom.coords, prec, False)
    return "".join(to_d(p, prec) for p in getattr(geom, "geoms", []))
P = lambda gj: transform(TF, shape(gj))
L = g["layers"]; S = g.setdefault("stats", {})

# --- Kumano Kodo: surveyed/official (OSM relations Nakahechi+Kohechi; Mie Iseji KML) vs rebuilt on OSM network
kr = {f["properties"]["route"]: f for f in json.load(open("kodo_routes.geojson"))["features"]}
iseji = P(kr["iseji"]["geometry"])
L["kodo_iseji"] = to_d(linemerge(iseji).simplify(25), 1)
rebuilt = [P(kr[k]["geometry"]).simplify(25) for k in ("okugake", "ohechi") if k in kr]
L["kodo_routed"] = to_d(MultiLineString([l for l in rebuilt]), 1) if rebuilt else ""
S["kodo_routed"] = sorted(kr)
# --- tsunami walking distance bands + landslide-exposed roads
l2 = json.load(open("layers2.json"))
for k in ("ts_d300", "ts_d600", "ts_dfar"): L[k] = to_d(P(l2[k]).simplify(4), 2)
L["ls_roads"] = to_d(P(l2["ls_roads"]).simplify(6), 1)
S["ts_pt_dist"] = l2.get("pt_dist", {})
S.update(l2.get("stats", {}))   # ts_walk (walking-distance shares) + ls_roads (road km inside landslide zones)
# --- flows
fl = json.load(open("flows.json"))
for k, v in fl.items(): L[k] = to_d(P(v), 1)
# --- official Ichida basin (digitised from MLIT 図-1.2)
ib = json.load(open("ichida/ichida_basin.json"))
L["ichida_basin"] = to_d(P(ib["ichida_basin"]), 2)
S["ichida_basin_km2_digitised"] = ib["area_km2"]
# --- Ichida river line + Ichida L2 flood, old-town micro relief
ic = json.load(open("ichida.json"))
L["ichida_line"] = to_d(P(ic["ichida_line"]).simplify(4), 2)
fl_i = [shape(f["geometry"]).buffer(0) for f in json.load(open("ksj/20_想定最大規模/A31a-20-25_86_8606010002_10.geojson", encoding="utf-8"))["features"]]
L["flood_ichida"] = to_d(transform(TF, unary_union(fl_i)).simplify(4), 2)
micro = ic["micro"]
L["micro_low"] = to_d(unary_union([P(micro[str(k)]) for k in (3, 5, 7) if micro.get(str(k))]), 2)
L["micro_high"] = to_d(unary_union([P(micro[str(k)]) for k in (10, 20, 40) if micro.get(str(k))]), 2)
json.dump(g, open("geo.json", "w"), ensure_ascii=False)
for k in ("kodo_iseji", "kodo_routed", "ts_d300", "ts_d600", "ts_dfar", "ls_roads", "flow_kitayama", "flow_kumano", "sea_osaka", "sea_edo", "ichida_line", "flood_ichida", "micro_low", "micro_high"):
    print(f"{k:14s} {len(L.get(k, ''))/1024:7.1f} KB")

# ---------------- extra camera views + named points for the second-round page -----------------
from shapely.geometry import Polygon as _Poly
def _dbox(w, s, e, n, k=8):
    pts = ([(w + (e - w) * i / k, s) for i in range(k)] + [(e, s + (n - s) * i / k) for i in range(k)] +
           [(e - (e - w) * i / k, n) for i in range(k)] + [(w, n - (n - s) * i / k) for i in range(k)])
    return transform(TF, _Poly(pts))
def vbox(w, s, e, n):
    a, b, c, d = _dbox(w, s, e, n).bounds
    return [round(sx(a), 1), round(sy(d), 1), round(sx(c), 1), round(sy(b), 1)]
g["views"].update({
    "oldtown": vbox(135.974, 33.716, 136.012, 33.744),
    "river": vbox(135.75, 33.70, 136.04, 33.87),
    "valleys": vbox(135.79, 33.70, 136.02, 33.86),
    "pathways": vbox(135.905, 33.668, 136.06, 33.785),
    "hinterland": vbox(135.30, 33.40, 136.42, 34.43),
    "ichida": [668.0, 794.0, 714.0, 834.0],   # svg units: the Ichida-gawa basin (673–707 × 799–829) with a margin
})
PTS2 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pts2.json")))   # sourced in kansai/qa/points.toml
for k, (lon, lat) in PTS2.items():
    X, Y = TF(lon, lat); g["pts"][k] = [round(sx(X), 2), round(sy(Y), 2)]
json.dump(g, open("geo.json", "w"), ensure_ascii=False)
print("views", sorted(g["views"]), "pts", len(g["pts"]))
