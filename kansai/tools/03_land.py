"""Land polygon from the OSM coastline: polygonize coastline + sheet edge, keep pieces whose DEM
samples are mostly above 1 m. Writes land.geojson."""
import json, numpy as np
from shapely.geometry import LineString, Polygon, box, mapping, shape
from shapely.ops import linemerge, unary_union, polygonize
S, Wl, N, E = 33.38, 135.25, 34.45, 136.42
bb = box(Wl, S, E, N)
js = json.load(open("osm/coast.json"))
lines = [LineString([(p["lon"], p["lat"]) for p in el["geometry"]]) for el in js["elements"] if el["type"] == "way" and len(el.get("geometry", [])) > 1]
print("ways", len(lines))
merged = linemerge(lines)
geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
print("merged", len(geoms), "closed", sum(g.is_closed for g in geoms))
clipped = unary_union([g.intersection(bb) for g in geoms] + [bb.boundary])
pieces = list(polygonize(clipped))
print("pieces", len(pieces))
dem = np.load("dem1.npy")
def elev(lon, lat):
    r = int(round((35.0 - lat) * 3600)); c = int(round((lon - 135.0) * 3600))
    return dem[r, c]
land = []
for p in pieces:
    # sample up to 60 interior points
    minx, miny, maxx, maxy = p.bounds
    rng = np.random.default_rng(0)
    pts = []
    tries = 0
    while len(pts) < 40 and tries < 4000:
        tries += 1
        x = rng.uniform(minx, maxx); y = rng.uniform(miny, maxy)
        from shapely.geometry import Point
        if p.contains(Point(x, y)): pts.append(elev(x, y))
    if not pts:
        pts = [elev(*p.representative_point().coords[0])]
    m = float(np.mean(pts)); frac = float(np.mean(np.array(pts) > 1))
    is_land = frac > 0.5
    if p.area > 0.01 or is_land: print(round(p.area, 5), "mean", round(m, 1), "frac>1", round(frac, 2), "LAND" if is_land else "sea")
    if is_land: land.append(p)
L = unary_union(land)
print("land parts", len(getattr(L, "geoms", [L])), "area deg2", L.area)
json.dump(mapping(L), open("land.geojson", "w"))
