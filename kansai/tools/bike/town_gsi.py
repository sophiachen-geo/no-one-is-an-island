"""Decode GSI optimal vector tiles (optimal_bvmap-v1, z16) for the town into metric geometries (JGD2011 / CS VI)."""
import os, glob, math, mapbox_vector_tile
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import transform
from pyproj import Transformer
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
D = os.path.join(os.getcwd(), "town", "obv16")
def _ll(tx, ty, ext, x, y, z=16):
    n = 2 ** z
    X = (tx + x / ext) / n; Y = (ty + y / ext) / n
    return X * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y))))
def layers(names=("RdCL", "RdEdg", "WA", "WL", "BldA")):
    out = {k: [] for k in names}
    for f in sorted(glob.glob(os.path.join(D, "16_*.pbf"))):
        if not os.path.getsize(f): continue
        _, tx, ty = os.path.basename(f)[:-4].split("_"); tx, ty = int(tx), int(ty)
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        for k in names:
            L = t.get(k)
            if not L: continue
            ext = L["extent"]
            for ft in L["features"]:
                g = ft["geometry"]; ty_ = g["type"]; cs = g["coordinates"]
                conv = lambda ring: [TR(*_ll(tx, ty, ext, x, y)) for x, y in ring]
                try:
                    if ty_ == "LineString": geoms = [LineString(conv(cs))]
                    elif ty_ == "MultiLineString": geoms = [LineString(conv(c)) for c in cs]
                    elif ty_ == "Polygon": geoms = [Polygon(conv(cs[0]), [conv(h) for h in cs[1:]])]
                    elif ty_ == "MultiPolygon": geoms = [Polygon(conv(p[0]), [conv(h) for h in p[1:]]) for p in cs]
                    else: continue
                except Exception:
                    continue
                for g2 in geoms:
                    if not g2.is_empty: out[k].append((g2, ft["properties"]))
    return out
