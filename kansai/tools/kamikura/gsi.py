"""GSI optimal vector tiles (experimental_bvmap, z16) → shapely geometries in JGD2011 / CS VI metres.

Tiles are read from a local cache (default ../morph/raw/bvmap/z16, as written by the main Kansai build).
Layers kept (ftCode in brackets):
  road_edge   road edges at 1:2,500 (2201 道路縁; 2203/2204/2221 other edge kinds), as (code, line)
  water_edge  water edges (5201 水涯線, 5203), as (code, line)
  bld         building outlines (3101/3102/3111 polygons)
  points      levelling benchmarks (7103), triangulation points (7102), spot heights (7201): (lon, lat, h, code)
"""
import glob, math, os
import numpy as np
import mapbox_vector_tile, shapely
from shapely.geometry import shape
from pyproj import Transformer

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
BBOX = (135.9760, 33.7165, 135.9990, 33.7315)


def tiles_layers(bbox=BBOX, tiles="../morph/raw/bvmap/z16"):
    out = {"road_edge": [], "water_edge": [], "bld": [], "points": []}
    for f in sorted(glob.glob(f"{tiles}/16_*.pbf")):
        z, tx, ty = map(int, os.path.basename(f)[:-4].split("_")); n = 2 ** z
        lon0, lon1 = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
        lat1, lat0 = (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n)))) for yy in (ty, ty + 1))
        if lon1 < bbox[0] or lon0 > bbox[2] or lat1 < bbox[1] or lat0 > bbox[3]: continue
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        for lname, L in t.items():
            ext = L["extent"]
            def tocs(c, tx=tx, ty=ty, ext=ext):
                x = (tx + c[:, 0] / ext) / n; y = (ty + c[:, 1] / ext) / n
                lon = x * 360 - 180; lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y))))
                X, Y = LL2P.transform(lon, lat); return np.column_stack([X, Y])
            for ft in L["features"]:
                p = ft["properties"]; code = p.get("ftCode"); gt = ft["geometry"]["type"]
                if lname == "road" and code in (2201, 2203, 2204, 2221):
                    out["road_edge"].append((code, shapely.transform(shape(ft["geometry"]), tocs)))
                elif lname == "river" and code in (5201, 5203):
                    out["water_edge"].append((code, shapely.transform(shape(ft["geometry"]), tocs)))
                elif lname == "building" and gt in ("Polygon", "MultiPolygon"):
                    g = shapely.clip_by_rect(shapely.make_valid(shape(ft["geometry"])), 0, 0, ext, ext)
                    if not g.is_empty: out["bld"].append(shapely.transform(g, tocs))
                elif lname in ("symbol", "elevation") and code in (7102, 7103, 7201) and "alti" in p:
                    cx, cy = ft["geometry"]["coordinates"]
                    x = (tx + cx / ext) / n; y = (ty + cy / ext) / n
                    lon = x * 360 - 180; lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y))))
                    if bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]:
                        out["points"].append((round(lon, 6), round(lat, 6), float(p["alti"]), code, p.get("gcpCode")))
    out["points"] = sorted(set(out["points"]), key=lambda r: r[2])
    return out
