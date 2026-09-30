"""Trace the Kumano (Shingu River system) basin upstream from the river mouth and vectorise it.
Writes basin3.npy and basin.geojson. Expect ~2,365 km2 (official: 2,360 km2)."""
import numpy as np, json
g = json.load(open("grid3.json")); H, W, res = g["H"], g["W"], g["res"]
acc = np.load("acc3.npy"); par = np.load("par3.npy"); dem = np.load("dem3.npy")
def rc(lat, lon): return int(round((35.0 - lat) / res)), int(round((lon - 135.0) / res))
def ll(r, c): return 35.0 - r * res, 135.0 + c * res
r0, c0 = rc(33.72, 136.00)
win = acc[r0-60:r0+60, c0-60:c0+60]
k = np.unravel_index(np.argmax(win), win.shape)
ro, co = r0 - 60 + k[0], c0 - 60 + k[1]
print("outlet", ll(ro, co), "acc cells", acc[ro, co], "elev", dem[ro, co])
# top accumulation cells nearby to understand
flat = [(acc[r, c], r, c) for r in range(r0-60, r0+60) for c in range(c0-60, c0+60)]
flat.sort(reverse=True)
for a, r, c in flat[:8]: print(round(a), ll(r, c), dem[r, c])
# basin = all cells draining to outlet: walk down parent chain membership via reverse topological (children lists)
pf = par.ravel(); N = H * W
children_count = np.bincount(pf[pf >= 0], minlength=N)
# build CSR children
idx = np.argsort(pf, kind="stable"); sorted_par = pf[idx]
start = np.searchsorted(sorted_par, np.arange(N)); end = np.searchsorted(sorted_par, np.arange(N), side="right")
basin = np.zeros(N, dtype=bool); stack = [ro * W + co]; basin[stack[0]] = True
while stack:
    i = stack.pop()
    for j in idx[start[i]:end[i]]:
        if not basin[j]: basin[j] = True; stack.append(j)
B = basin.reshape(H, W)
# cell area km2
lats = 35.0 - (np.arange(H) + 0.5) * res
cell = (res * 111.32) * (res * 111.32 * np.cos(np.radians(lats)))
area = (B * cell[:, None]).sum()
print("basin cells", B.sum(), "area km2", round(area, 1))
np.save("basin3.npy", B)
rows, cols = np.where(B); print("bbox lat", ll(rows.max(), 0)[0], ll(rows.min(), 0)[0], "lon", ll(0, cols.min())[1], ll(0, cols.max())[1])

# ---- vectorise
from skimage import measure
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union
g = json.load(open("grid3.json")); res = g["res"]
B = np.load("basin3.npy").astype(float)
P = np.pad(B, 1)
cs = measure.find_contours(P, 0.5)
polys = []
for c in cs:
    # c in (row, col) of padded grid -> cell centre coords: row r => lat 35 - (r-1+0.5)*res
    lat = 35.0 - (c[:, 0] - 1 + 0.5) * res
    lon = 135.0 + (c[:, 1] - 1 + 0.5) * res
    if len(c) > 10:
        polys.append(Polygon(np.c_[lon, lat]).buffer(0))
polys.sort(key=lambda p: -p.area)
print("rings", len(polys), [round(p.area, 5) for p in polys[:5]])
basin = polys[0]
# drop holes smaller than ~0.5 km2
basin = Polygon(basin.exterior, [h for h in basin.interiors if Polygon(h).area > 5e-5])
json.dump(mapping(basin), open("basin.geojson", "w"))
print("basin bounds", basin.bounds, "holes", len(basin.interiors))
