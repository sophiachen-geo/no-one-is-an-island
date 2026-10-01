"""Polygons from the digitised 2026 tsunami depth grids (1 m, EPSG:6674): one MultiPolygon per depth class, clipped to the
municipality the map is valid for, simplified by 1 m, written as GeoJSON in JGD2011 lon/lat (EPSG:6668).
usage: vectorize.py <grid.npz> <N03 geojson> <municipality> <scenario> <source> <out.geojson>"""
import sys, json, numpy as np
import rasterio.features, affine
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as tfm
from pyproj import Transformer
src, n03, muni, scen, source, out = sys.argv[1:7]
TR = Transformer.from_crs(6668, 6674, always_xy=True).transform; TI = Transformer.from_crs(6674, 6668, always_xy=True).transform
Z = np.load(src); g = Z["grid"]; e0 = float(Z["e0"]); n1 = float(Z["n1"])
T = affine.Affine(1.0, 0, e0, 0, -1.0, n1)
M = tfm(TR, unary_union([shape(f["geometry"]) for f in json.load(open(n03, encoding="utf-8"))["features"] if f["properties"].get("N03_004") == muni]))
inside = rasterio.features.rasterize([(M, 1)], out_shape=g.shape, transform=T, fill=0, dtype="uint8").astype(bool)
LO = [0, 0.01, 0.3, 0.5, 1, 3, 5, 10, 20]; HI = [0, 0.3, 0.5, 1, 3, 5, 10, 20, None]
feats = []; tot = 0.0
for c in range(1, int(g.max()) + 1):
    m = (g == c) & inside
    if not m.any(): continue
    polys = [shape(s) for s, v in rasterio.features.shapes(m.astype(np.uint8), mask=m, transform=T) if v == 1]
    u = unary_union(polys).simplify(1.0, preserve_topology=True).buffer(0)
    a = float(m.sum()) / 1e4; tot += a
    feats.append({"type": "Feature", "properties": {"scenario": scen, "class": c, "depth_min_m": LO[c], "depth_max_m": HI[c], "area_ha": round(a, 2),
                                                     "source": source, "note": "digitised from the published PDF map (colour classes); not an official GIS release"},
                  "geometry": mapping(tfm(TI, u))})
json.dump({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::6668"}}, "features": feats},
          open(out, "w"), ensure_ascii=False)
print(out, "classes", len(feats), "area ha", round(tot, 1))
