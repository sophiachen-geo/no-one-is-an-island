"""Residents per building, Shingū and Kihō, 2020 census (dasymetric).

Buildings: GSI 電子国土基本情報 building outlines (optimal_bvmap-v1 z16, BldA), parts cut by tile edges re-joined.
People:   2020 census 250 m mesh (T001142: total, 65+, 75+) and small areas (町丁・字, T001082: total, 65+, 75+),
          as published. Suppressed mesh cells (HTKSYORI 2) report their total but pass their ages to a receiving cell;
          the receiving cell's ages are spread over the group in proportion to population.
Weights:  footprint area, 15–2,500 m²; zero for open sheds (無壁舎) and for buildings inside OpenStreetMap sites
          that are not homes (schools, temples and shrines, industry, retail, offices, stations, hospitals, …).
          A cell with people but no weighted building falls back to all its buildings, then to its centre.
Fit:      iterative proportional fitting so every mesh cell and every small area adds up to its census count
          (total, 65+, 75+ separately).
Output:   bld.npz — per building: x, y (EPSG:6674 centroid), area, code, muni (1 Shingū, 2 Kihō, 0 other), pop, p65, p75,
          cell index, small-area index; bld_shapes.pkl — footprints."""
import json, math, glob, os, pickle, sys, collections
import numpy as np
from shapely.geometry import shape, Point, box, LineString
from shapely.ops import unary_union, transform as tfm
from shapely.strtree import STRtree
from shapely.prepared import prep
from pyproj import Transformer
import cfg
sys.path.insert(0, cfg.BIKE)
import town_gsi
town_gsi.D = os.path.abspath("obv16")          # fetch_bld.py
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
TI = Transformer.from_crs(6674, 4326, always_xy=True).transform
# ---------------------------------------------------------------- buildings
L = town_gsi.layers(("BldA",))["BldA"]
polys = [(g.buffer(0), p.get("vt_code")) for g, p in L if g.area > 0.5]
print("BldA parts", len(polys), file=sys.stderr)
# z16 tile edges (lines of constant lon / lat) inside the area
def tile_edges():
    xs, ys = set(), set()
    for f in glob.glob("obv16/16_*.pbf"):
        _, x, y = os.path.basename(f)[:-4].split("_"); xs.add(int(x)); ys.add(int(y))
    n = 2 ** 16
    lon = lambda x: x / n * 360 - 180
    lat = lambda y: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    lines = []
    for x in range(x0, x1 + 1):
        lines.append(LineString([TR(lon(x), lat(y0) + 0.0), TR(lon(x), lat(y1))]))
    for y in range(y0, y1 + 1):
        lines.append(LineString([TR(lon(x0), lat(y)), TR(lon(x1), lat(y))]))
    return unary_union(lines)
EDGES = prep(tile_edges().buffer(0.25))
near = [i for i, (g, c) in enumerate(polys) if EDGES.intersects(g)]
# union parts that touch across an edge: cluster near-edge parts whose 5 cm buffers intersect
tree = STRtree([polys[i][0] for i in near])
parent = list(range(len(near)))
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
    return a
for k, i in enumerate(near):
    g = polys[i][0].buffer(0.05)
    for j in tree.query(g):
        if j != k and g.intersects(polys[near[j]][0]) and EDGES.intersects(g.intersection(polys[near[j]][0].buffer(0.05))):
            parent[find(k)] = find(int(j))
groups = collections.defaultdict(list)
for k in range(len(near)): groups[find(k)].append(near[k])
merged = []
done = set(near)
for gk, idx in groups.items():
    g = unary_union([polys[i][0].buffer(0.05) for i in idx]).buffer(-0.05)
    code = collections.Counter(polys[i][1] for i in idx).most_common(1)[0][0]
    for part in (g.geoms if hasattr(g, "geoms") else [g]):
        if part.area > 0.5: merged.append((part, code))
B = [(g, c) for i, (g, c) in enumerate(polys) if i not in done] + merged
print("buildings after re-joining", len(B), "(near-edge parts", len(near), "->", len(merged), ")", file=sys.stderr)
# ---------------------------------------------------------------- municipalities
def muni_poly(fn, name):
    d = json.load(open(fn, encoding="utf-8"))
    return tfm(TR, unary_union([shape(f["geometry"]) for f in d["features"] if f["properties"].get("N03_004") == name]))
SH = muni_poly(cfg.geo("ksj", "N03-20260101_30.geojson"), "新宮市"); KI = muni_poly(cfg.geo("ksj", "N03-20260101_24.geojson"), "紀宝町")
SHp, KIp = prep(SH), prep(KI)
# ---------------------------------------------------------------- non-residential sites (OSM, 2026-10-01)
osm = json.load(open(cfg.dl("osm_nonres.json")))
NR = []
for e in osm["elements"]:
    if e["type"] == "way" and e.get("geometry") and len(e["geometry"]) >= 4:
        cs = [TR(p["lon"], p["lat"]) for p in e["geometry"]]
        if cs[0] == cs[-1]:
            from shapely.geometry import Polygon
            pg = Polygon(cs).buffer(0)
            t = e.get("tags", {})
            if t.get("leisure") == "park" or t.get("amenity") == "parking": pass
            NR.append(pg)
    elif e["type"] == "relation":
        outers = [m for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        from shapely.geometry import Polygon
        from shapely.ops import polygonize
        ls = [LineString([TR(p["lon"], p["lat"]) for p in m["geometry"]]) for m in outers]
        for pg in polygonize(unary_union(ls)): NR.append(pg.buffer(0))
NRu = prep(unary_union(NR))
print("OSM non-residential polygons", len(NR), osm["osm3s"]["timestamp_osm_base"], file=sys.stderr)
# ---------------------------------------------------------------- census
def mesh_code(lon, lat):
    p = int(lat * 1.5); u = int(lon - 100)
    la = lat - p / 1.5; lo = lon - (u + 100)
    q = int(la / (5 / 60)); v = int(lo / (7.5 / 60)); la -= q * 5 / 60; lo -= v * 7.5 / 60
    r = int(la / (30 / 3600)); w = int(lo / (45 / 3600)); la -= r * 30 / 3600; lo -= w * 45 / 3600
    code = f"{p:02d}{u:02d}{q}{v}{r}{w}"
    dla, dlo = 30 / 3600, 45 / 3600
    for _ in range(2):
        dla /= 2; dlo /= 2
        a = 1 if la >= dla else 0; b = 1 if lo >= dlo else 0
        code += str(1 + b + 2 * a); la -= a * dla; lo -= b * dlo
    return code
M = json.load(open("derived_mesh250_2020_shingu_kiho.geojson", encoding="utf-8"))["features"]
cells = {f["properties"]["mesh250"]: f["properties"] for f in M}
# age groups: receiving cell (HTKSYORI 1) + its donors (2)
grp = {}
for c, p in cells.items():
    grp[c] = p["htksaki"] if p["htksyori"] == "2" and p["htksaki"] else c
def cell_age(k):
    out = {}
    members = collections.defaultdict(list)
    for c, g in grp.items(): members[g].append(c)
    for g, ms in members.items():
        rec = cells.get(g)
        val = rec.get(k) if rec else None
        tot = sum(cells[m]["pop_total"] or 0 for m in ms)
        for m in ms:
            out[m] = (val or 0) * (cells[m]["pop_total"] or 0) / tot if (val is not None and tot > 0) else None
    return out
age65 = cell_age("age65p"); age75 = cell_age("age75p")
missing65 = [c for c in cells if age65[c] is None and (cells[c]["pop_total"] or 0) > 0]
print("cells with no age data after grouping", len(missing65), sum(cells[c]["pop_total"] for c in missing65), file=sys.stderr)
SA = json.load(open("derived_smallarea_age_2020_shingu_kiho.geojson", encoding="utf-8"))["features"]
SAg = [tfm(TR, shape(f["geometry"])) for f in SA]
SAt = STRtree(SAg)
# ---------------------------------------------------------------- per building
n = len(B)
X = np.zeros(n); Y = np.zeros(n); A = np.zeros(n); CODE = np.zeros(n, int); MU = np.zeros(n, np.int8)
CELL = np.empty(n, object); SAI = np.full(n, -1); W = np.zeros(n); NRES = np.zeros(n, bool)
for i, (g, c) in enumerate(B):
    pt = g.representative_point(); X[i], Y[i] = pt.x, pt.y; A[i] = g.area; CODE[i] = c or 0
    MU[i] = 1 if SHp.contains(pt) else (2 if KIp.contains(pt) else 0)
    lon, lat = TI(pt.x, pt.y); CELL[i] = mesh_code(lon, lat)
    for j in SAt.query(pt):
        if SAg[j].contains(pt): SAI[i] = int(j); break
    NRES[i] = NRu.contains(pt)
    W[i] = A[i] if (15 <= A[i] <= 2500 and CODE[i] not in (3111, 3112) and not NRES[i]) else 0.0
print("buildings", n, "weighted", int((W > 0).sum()), "non-residential sites", int(NRES.sum()), "open sheds", int(np.isin(CODE, (3111, 3112)).sum()), file=sys.stderr)
# initial allocation per cell (with fallbacks)
by_cell = collections.defaultdict(list)
for i in range(n): by_cell[CELL[i]].append(i)
pseudo = []
w0 = W.copy()
for c, p in cells.items():
    pop = p["pop_total"] or 0
    if pop <= 0: continue
    ids = by_cell.get(c, [])
    if ids and w0[ids].sum() == 0:
        for i in ids: w0[i] = max(A[i], 1.0)
    if not ids: pseudo.append(c)
print("populated cells with no building at all", len(pseudo), [cells[c]["pop_total"] for c in pseudo], file=sys.stderr)
def ipf(cell_tot, sa_tot, iters=200):
    v = np.zeros(n)
    for c, ids in by_cell.items():
        t = cell_tot.get(c) or 0; s = w0[ids].sum()
        if t > 0 and s > 0: v[ids] = t * w0[ids] / s
    for it in range(iters):
        # small areas
        for j, t in sa_tot.items():
            ids = np.nonzero(SAI == j)[0]; s = v[ids].sum()
            if s > 0 and t is not None: v[ids] *= t / s
        # cells
        dev = 0.0
        for c, ids in by_cell.items():
            t = cell_tot.get(c) or 0; s = v[ids].sum()
            if s > 0: dev = max(dev, abs(s - t)); v[ids] *= t / s
        if dev < 0.01: break
    sadev = max((abs(v[SAI == j].sum() - t) for j, t in sa_tot.items() if t is not None), default=0)
    return v, it, dev, sadev
cell_pop = {c: p["pop_total"] for c, p in cells.items()}
sa_pop = {j: f["properties"]["pop_total"] for j, f in enumerate(SA)}
pop, it, dev, sadev = ipf(cell_pop, sa_pop)
print("IPF total: iterations", it, "max cell dev", round(dev, 3), "max small-area dev", round(sadev, 3), file=sys.stderr)
p65, it, dev, sadev = ipf({c: age65[c] for c in cells}, {j: f["properties"]["age65p"] for j, f in enumerate(SA)})
print("IPF 65+: iterations", it, "max cell dev", round(dev, 3), "max small-area dev", round(sadev, 3), file=sys.stderr)
p75, it, dev, sadev = ipf({c: age75[c] for c in cells}, {j: f["properties"]["age75p"] for j, f in enumerate(SA)})
print("IPF 75+: iterations", it, "max cell dev", round(dev, 3), "max small-area dev", round(sadev, 3), file=sys.stderr)
np.savez_compressed("bld.npz", x=X, y=Y, area=A, code=CODE, muni=MU, pop=pop, p65=p65, p75=p75, cell=CELL.astype(str), sa=SAI, w=W, nres=NRES)
pickle.dump([g for g, c in B], open("bld_shapes.pkl", "wb"))
res = {}
for m, name in ((1, "Shingu"), (2, "Kiho"), (0, "other")):
    k = MU == m
    res[name] = {"buildings": int(k.sum()), "residential_weighted": int((k & (W > 0)).sum()), "pop": round(float(pop[k].sum())), "p65": round(float(p65[k].sum())), "p75": round(float(p75[k].sum()))}
print(json.dumps(res))
