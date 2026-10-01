"""Length of each corridor inside hazard areas (metres, in JGD2011 / CS VI).
Layers are loaded lazily: A33 sediment-disaster warning zones (Aug 2025; yellow = 警戒区域, red = 特別警戒区域),
A40 tsunami inundation (prefectural L2 assumption as distributed in KSJ), A31a river flood (max class)."""
import json, glob, os, zipfile, io
import shapefile
from shapely.geometry import shape, LineString, MultiLineString
from shapely.strtree import STRtree
from shapely.ops import transform
from pyproj import Transformer
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
KSJ = "/tmp/claude-0/-home-user-no-one-is-an-island/12597f4f-a471-563e-939e-90ea1b9703e1/scratchpad/geo/ksj"
BB = (135.70, 33.60, 136.06, 33.92)
def _in_bb(g):
    x0, y0, x1, y1 = g.bounds
    return not (x1 < BB[0] or x0 > BB[2] or y1 < BB[1] or y0 > BB[3])
def _proj(geoms):
    out = [transform(TR, g.buffer(0) if not g.is_valid else g) for g in geoms]
    return out, STRtree(out)
def landslide():
    red, yel = [], []
    for f in ("A33-25_24Polygon.geojson", "A33-25_30Polygon.geojson"):
        for ft in json.load(open(os.path.join(KSJ, f), encoding="utf-8"))["features"]:
            g = shape(ft["geometry"])
            if not _in_bb(g): continue
            p = ft["properties"]
            # A33_002: 1/3 警戒区域 (yellow), 2/4 特別警戒区域 (red) — same rule as tools/07_build.py
            (red if p["A33_002"] in (2, 4) else yel).append(g)
    return {"ls_red": _proj(red), "ls_yellow": _proj(yel)}
def length_in(line_ll, layer):
    geoms, tree = layer
    L = transform(TR, LineString(line_ll))
    tot = 0.0
    hit = [geoms[i] for i in tree.query(L)]
    if not hit: return 0.0
    from shapely.ops import unary_union
    U = unary_union([g for g in hit if g.intersects(L)])
    return L.intersection(U).length if not U.is_empty else 0.0
def flood():
    gs = []
    for fn in ("8606010001", "8606010002", "8606010006"):
        for ft in json.load(open(os.path.join(KSJ, "20_想定最大規模", f"A31a-20-25_86_{fn}_10.geojson"), encoding="utf-8"))["features"]:
            g = shape(ft["geometry"])
            if _in_bb(g): gs.append(g)
    return {"flood_max": _proj(gs)}
def tsunami():
    gs = []
    for ft in json.load(open(os.path.join(KSJ, "A40-16_30_GML", "A40-16_30.geojson"), encoding="utf-8"))["features"]:
        g = shape(ft["geometry"])
        if _in_bb(g): gs.append(g)
    sf = shapefile.Reader(os.path.join(KSJ, "A40-16_24_GML", "A40-16_24.shp"), encoding="cp932")
    for sr in sf.iterShapeRecords():
        g = shape(sr.shape.__geo_interface__)
        if _in_bb(g): gs.append(g)
    return {"tsunami_l2_2016": _proj(gs)}
