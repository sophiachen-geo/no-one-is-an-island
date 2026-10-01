"""Extra analytical layer: roads crossing designated landslide zones. Writes layers2.json (lon/lat geometries) + prints stats.
(The walking distance to dry ground that this step used to compute is replaced by the per-building evacuation margins
of tools/risk.)"""
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

out["stats"] = {}

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
