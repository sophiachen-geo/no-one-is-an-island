"""Ichida-gawa catchment from the GSI 5 m DEM (priority-flood + D8, seeded by the sea and the Kumano River
water surface), plus old-town micro-relief contours. Writes ichida.json (lon/lat)."""
import json, math, heapq, time, numpy as np, shapely
from shapely.geometry import shape, Polygon, LineString, Point, mapping, box
from shapely.ops import unary_union, linemerge
from scipy.ndimage import gaussian_filter
from skimage import measure
g = np.load("gsi_dem5.npy"); meta = json.load(open("gsi_dem5.json"))
Z, tx0, ty0 = meta["z"], meta["tx0"], meta["ty0"]; H, W = g.shape
def px2ll(r, c):
    n = 2 ** Z; x = tx0 + (c + 0.5) / 256; y = ty0 + (r + 0.5) / 256
    lon = x / n * 360 - 180; lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat
def ll2px(lon, lat):
    n = 2 ** Z; x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return (y - ty0) * 256 - 0.5, (x - tx0) * 256 - 0.5
# seeds: no-data (sea) + Kumano River water polygon cells + the grid edge
water = []
for el in json.load(open("osm/city_water.json"))["elements"]:
    if el["type"] == "way" and len(el.get("geometry", [])) > 3:
        c = [(p["lon"], p["lat"]) for p in el["geometry"]]
        if c[0] == c[-1]:
            pg = Polygon(c).buffer(0)
            if pg.area > 2e-6: water.append(pg)
WATER = unary_union(water)
rows = np.arange(H); cols = np.arange(W)
# lon/lat of pixel centres (separable in web mercator)
n = 2 ** Z
lons = (tx0 + (cols + 0.5) / 256) / n * 360 - 180
lats = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (ty0 + (rows + 0.5) / 256) / n))))
LON, LAT = np.meshgrid(lons, lats)
waterm = shapely.contains_xy(WATER, LON.ravel(), LAT.ravel()).reshape(H, W)
sea = np.isnan(g)
elev = np.where(sea, -5.0, g).astype(np.float64)
seed = sea | waterm
t0 = time.time()
flat = elev.ravel().tolist(); N = H * W
parent = np.full(N, -1, dtype=np.int64); seen = np.zeros(N, dtype=bool)
pq = [(flat[i], i) for i in np.flatnonzero(seed.ravel())]
for i in np.flatnonzero(seed.ravel()): seen[i] = True
for r in (0, H - 1):
    for c in range(W):
        i = r * W + c
        if not seen[i]: seen[i] = True; pq.append((flat[i], i))
for c in (0, W - 1):
    for r in range(H):
        i = r * W + c
        if not seen[i]: seen[i] = True; pq.append((flat[i], i))
heapq.heapify(pq)
order = []
nb = (-W - 1, -W, -W + 1, -1, 1, W - 1, W, W + 1)
while pq:
    e, i = heapq.heappop(pq); order.append(i)
    r, c = divmod(i, W)
    for d in nb:
        j = i + d
        if j < 0 or j >= N: continue
        rr, cc = divmod(j, W)
        if abs(rr - r) > 1 or abs(cc - c) > 1 or seen[j]: continue
        seen[j] = True
        fj = flat[j] if flat[j] > e else e + 1e-5
        parent[j] = i
        heapq.heappush(pq, (fj, j))
print("flood", round(time.time() - t0, 1), "s")
# Ichida outlet: downstream end of OSM 市田川 nearest the Kumano water
rv = json.load(open("osm/rivers.json"))["elements"]
ich = [LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in rv if e["type"] == "way" and e.get("tags", {}).get("name") == "市田川"]
ichl = linemerge(unary_union(ich)); ends = []
for part in getattr(ichl, "geoms", [ichl]):
    ends += [Point(part.coords[0]), Point(part.coords[-1])]
mouth = min(ends, key=lambda p: p.distance(WATER))
print("Ichida mouth", round(mouth.x, 5), round(mouth.y, 5), "dist to water deg", mouth.distance(WATER))
# outlet zone = land cells within ~25 m of the last ~300 m of the Ichida channel
part = min(getattr(ichl, "geoms", [ichl]), key=lambda p: min(Point(p.coords[0]).distance(mouth), Point(p.coords[-1]).distance(mouth)))
if Point(part.coords[0]).distance(mouth) < Point(part.coords[-1]).distance(mouth):
    part = LineString(part.coords[::-1])
from shapely.ops import substring
tail = substring(part, max(0, part.length - 0.003), part.length)          # ~300 m in degrees
zone = tail.buffer(0.00025)                                                 # ~25 m
outlet = set(np.flatnonzero((shapely.contains_xy(zone, LON.ravel(), LAT.ravel()) & ~seed.ravel())).tolist())
print("outlet cells", len(outlet))
basin = np.zeros(N, dtype=bool)
outl = np.zeros(N, dtype=bool); outl[list(outlet)] = True
for i in order:                       # order is downstream-first: a cell's parent is always earlier
    p = parent[i]
    basin[i] = outl[i] or (p >= 0 and basin[p])
B = basin.reshape(H, W) & ~seed
px_area = []
lat_c = LAT.mean(); mx = 360 / n / 256 * 111320 * math.cos(math.radians(lat_c)); my = mx
print("Ichida catchment km2 ≈", round(B.sum() * mx * my / 1e6, 2))
polys = []
for c in measure.find_contours(np.pad(gaussian_filter(B.astype(float), 1.2), 1), 0.5):
    if len(c) < 20: continue
    pts = [px2ll(rr - 1, cc - 1) for rr, cc in c]
    polys.append(Polygon(pts).buffer(0))
polys.sort(key=lambda p: -p.area)
basin_poly = polys[0] if polys else Polygon()
# micro-relief contours in the old town window (natural levee, castle hill, dune ridge)
OW = (135.975, 33.712, 136.012, 33.745)
ra0, ca0 = ll2px(OW[0], OW[3]); ra1, ca1 = ll2px(OW[2], OW[1])
sub = gaussian_filter(np.where(sea, -5, g)[int(ra0):int(ra1), int(ca0):int(ca1)], 1.4)
micro = {}
for lv in (3, 5, 7, 10, 20, 40):
    ls = []
    for c in measure.find_contours(sub, lv):
        if len(c) < 12: continue
        ls.append(LineString([px2ll(rr + int(ra0), cc + int(ca0)) for rr, cc in c]))
    micro[lv] = mapping(unary_union(ls).simplify(0.00003)) if ls else None
json.dump({"ichida_basin": mapping(basin_poly), "ichida_mouth": [mouth.x, mouth.y], "ichida_line": mapping(ichl), "micro": micro}, open("ichida.json", "w"))
print("written; basin polygon area deg2", basin_poly.area)
