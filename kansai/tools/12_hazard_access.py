"""Extra analytical layers: (a) walking distance from L2-inundated land to the nearest dry ground,
(b) roads crossing designated landslide zones. Writes layers2.json (lon/lat geometries) + prints stats."""
import json, math, numpy as np, shapely
from shapely.geometry import shape, box, Polygon, LineString, mapping, Point
from shapely.ops import unary_union, transform, linemerge
from skimage import measure, graph as skgraph
from scipy.ndimage import gaussian_filter, binary_dilation
from pyproj import Transformer
TF = Transformer.from_crs(6668, 6674, always_xy=True).transform
INV = Transformer.from_crs(6674, 6668, always_xy=True).transform
import shapefile
prefs = {k: shape(v) for k, v in json.load(open("prefs.geojson")).items()}
out = {}

# ---------------- (a) distance to dry ground inside the L2 tsunami area -----------------
WIN = (135.935, 33.662, 136.045, 33.768)
wb = box(*WIN)
ts_w = [shape(f["geometry"]).buffer(0) for f in json.load(open("ksj/A40-16_30_GML/A40-16_30.geojson", encoding="utf-8"))["features"] if shape(f["geometry"]).intersects(wb)]
sf = shapefile.Reader("ksj/A40-16_24_GML/A40-16_24.shp", encoding="cp932"); ts_m = []
for sr in sf.iterShapeRecords():
    bx = sr.shape.bbox
    if bx[2] < WIN[0] or bx[0] > WIN[2] or bx[3] < WIN[1] or bx[1] > WIN[3]: continue
    ts_m.append(shape(sr.shape.__geo_interface__).buffer(0))
TSW = unary_union(ts_w).intersection(prefs["和歌山県"].buffer(0)); TSM = unary_union(ts_m).intersection(prefs["三重県"].buffer(0))
TS = transform(TF, TSW.union(TSM).intersection(wb))
TS = TS.buffer(12).buffer(-12)          # close slivers between depth-class polygons
land = transform(TF, shape(json.load(open("land.geojson"))).intersection(wb))
water = []
try:
    for el in json.load(open("osm/city_water.json"))["elements"]:
        if el["type"] == "way" and len(el.get("geometry", [])) > 3:
            c = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if c[0] == c[-1]: water.append(Polygon(c).buffer(0))
except FileNotFoundError: pass
WATER = transform(TF, unary_union(water).intersection(wb)) if water else Polygon()
CELL = 10.0
x0, y0, x1, y1 = transform(TF, wb).bounds
nx, ny = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
xs = x0 + (np.arange(nx) + 0.5) * CELL; ys = y1 - (np.arange(ny) + 0.5) * CELL
XX, YY = np.meshgrid(xs, ys)
landm = shapely.contains_xy(land.buffer(0), XX.ravel(), YY.ravel()).reshape(ny, nx)
waterm = shapely.contains_xy(WATER.buffer(0), XX.ravel(), YY.ravel()).reshape(ny, nx) if not WATER.is_empty else np.zeros_like(landm)
inund = shapely.contains_xy(TS.buffer(0), XX.ravel(), YY.ravel()).reshape(ny, nx)
walk = landm & ~waterm
dry = walk & ~inund
# a refuge must be a real patch of dry ground: keep dry components >= 1 ha
from scipy.ndimage import label
lab, n = label(dry)
sizes = np.bincount(lab.ravel()) * CELL * CELL
keep = sizes >= 10000; keep[0] = False
safe = keep[lab]
print("dry components", n, "kept as refuge", int(keep.sum()))
cost = np.where(walk, 1.0, np.inf)
mcp = skgraph.MCP_Geometric(cost)
starts = list(zip(*np.where(safe)))
dist, _ = mcp.find_costs(starts)
dist = dist * CELL
dist[~(walk & inund)] = np.nan
vals = dist[np.isfinite(dist)]
print("inundated walkable cells", vals.size, "share within 300 m", round(float((vals <= 300).mean()) * 100, 1), "within 600 m", round(float((vals <= 600).mean()) * 100, 1), "max m", round(float(vals.max())))
out["stats"] = {"ts_walk": {"share_le300_pct": round(float((vals <= 300).mean()) * 100, 1), "share_le600_pct": round(float((vals <= 600).mean()) * 100, 1),
                            "max_m": round(float(vals.max())), "cell_m": CELL, "refuge_min_ha": 1.0}}
def band(lo, hi):
    m = np.isfinite(dist) & (dist > lo) & (dist <= hi)
    m = gaussian_filter(m.astype(float), 0.8)
    rings = []
    for c in measure.find_contours(np.pad(m, 1), 0.5):
        px = x0 + (c[:, 1] - 1 + 0.5) * CELL; py = y1 - (c[:, 0] - 1 + 0.5) * CELL
        if len(c) > 5: rings.append(Polygon(np.c_[px, py]).buffer(0))
    rings.sort(key=lambda p: -p.area); acc = Polygon()
    for r in rings: acc = acc.symmetric_difference(r)
    acc = acc.intersection(TS.buffer(5))
    return acc
for key, lo, hi in (("ts_d300", 0, 300), ("ts_d600", 300, 600), ("ts_dfar", 600, 1e9)):
    g = band(lo, hi).simplify(6)
    out[key] = mapping(transform(INV, g)); print(key, "km2", round(g.area / 1e6, 3))
# distances for named points
PTS = {"station": (135.9941, 33.7251), "cityhall": (135.9925, 33.7241), "hayatama": (135.9837, 33.7323), "ukijima": (135.9907, 33.7259), "miwasaki_stn": (135.9848, 33.6894)}
def dist_at(lon, lat):
    x, y = TF(lon, lat); j = int((x - x0) / CELL); i = int((y1 - y) / CELL)
    v = dist[i, j] if 0 <= i < ny and 0 <= j < nx else np.nan
    return None if not np.isfinite(v) else round(float(v))
out["pt_dist"] = {k: dist_at(*v) for k, v in PTS.items() if v}
print("point distances", out["pt_dist"])
np.save("ts_dist.npy", dist); json.dump({"x0": x0, "y1": y1, "cell": CELL, "nx": nx, "ny": ny}, open("ts_dist.json", "w"))

# ---------------- (b) roads through landslide zones (whole Shingu window) -----------------
CW = (135.70, 33.60, 136.08, 33.95); cb = box(*CW)
zones = []
for fn in ("ksj/A33-25_30Polygon.geojson", "ksj/A33-25_24Polygon.geojson"):
    for f in json.load(open(fn, encoding="utf-8"))["features"]:
        g = shape(f["geometry"])
        if g.intersects(cb) and f["properties"]["A33_002"] in (1, 2, 3, 4): zones.append(g.buffer(0))
Z = transform(TF, unary_union(zones))
rd = json.load(open("osm/roads.json"))["elements"] + json.load(open("osm/city_roads.json"))["elements"]
roads = {}
for el in rd:
    if el["type"] != "way" or len(el.get("geometry", [])) < 2: continue
    t = el.get("tags", {}); ref = t.get("ref", ""); nm = t.get("name", "")
    g = LineString([(p["lon"], p["lat"]) for p in el["geometry"]])
    if not g.intersects(cb): continue
    key = ("NR168" if "168" in ref.split(";") else "NR42" if "42" in ref.split(";") and t.get("highway") == "trunk" else
           "NR311" if "311" in ref.split(";") else "E42" if t.get("highway") == "motorway" else "local")
    roads.setdefault(key, []).append(transform(TF, g.intersection(cb)))
shingu = transform(TF, shape(json.load(open("munis.geojson"))["和歌山県|新宮市|30207"]).buffer(0))
exposed = []
for k, ls in roads.items():
    m = unary_union(ls)
    inz = m.intersection(Z)
    tot_s = m.intersection(shingu).length / 1000; in_s = inz.intersection(shingu).length / 1000
    print(f"{k}: in Shingu {tot_s:.1f} km, of which in landslide zones {in_s:.1f} km ({100*in_s/max(tot_s,1e-9):.0f}%)")
    out["stats"].setdefault("ls_roads", {})[k] = {"km": round(tot_s, 1), "in_zone_km": round(in_s, 1), "pct": round(100 * in_s / max(tot_s, 1e-9), 1)}
    exposed.append(inz)
EXP = unary_union(exposed).intersection(shingu)
out["ls_roads"] = mapping(transform(INV, EXP.simplify(8)))
json.dump(out, open("layers2.json", "w"))
print("written")
