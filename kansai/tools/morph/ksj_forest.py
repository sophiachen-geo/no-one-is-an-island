import numpy as np, shapely, time, json, sys
from shapely.geometry import box, Polygon, MultiPolygon, mapping
from pyproj import Transformer, Geod
D = sys.argv[1]
z = np.load(f'{D}/raw/ksj/landuse_grid.npz'); g = z['grid']; lat0 = int(z['lat0']); lon0 = int(z['lon0'])
H, Wd = g.shape
W, S, E, N = 135.25, 33.38, 136.42, 34.45
# row/col -> lon/lat edges
def X(j): return 100 + (lon0 + j) / 800.0
def Y(i): return (lat0 + i) / 1200.0
# restrict grid to frame: cells whose centre lies within frame
ci = (np.arange(H) + 0.5); cj = (np.arange(Wd) + 0.5)
latc = (lat0 + ci) / 1200.0; lonc = 100 + (lon0 + cj) / 800.0
rowmask = (latc >= S) & (latc <= N); colmask = (lonc >= W) & (lonc <= E)
inframe = rowmask[:, None] & colmask[None, :]
# cell area on the GRS80 ellipsoid (exact band formula via authalic latitude approx using Geod on one cell per row)
geod = Geod(ellps='GRS80')
rowarea = np.array([abs(geod.polygon_area_perimeter([X(0), X(1), X(1), X(0)], [Y(i), Y(i), Y(i+1), Y(i+1)])[0]) / 1e6 for i in range(H)])
A = np.broadcast_to(rowarea[:, None], g.shape)
forest = (g == 500) & inframe
sea = (g == 1500) | (g == 0)
land = (~sea) & inframe
water = (g == 1100) & inframe
fa = A[forest].sum(); la = A[land].sum(); wa = A[water].sum()
print('forest km2 %.1f land km2 %.1f share %.4f share_excl_inland_water %.4f' % (fa, la, fa/la, fa/(la-wa)))
stats = dict(forest_km2=round(float(fa),1), land_km2=round(float(la),1), inland_water_km2=round(float(wa),1),
             forest_share=round(float(fa/la),4), forest_share_excl_inland_water=round(float(fa/(la-wa)),4),
             forest_cells=int(forest.sum()), land_cells=int(land.sum()))
# --- vectorise: horizontal runs per row -> boxes -> union
t = time.time()
boxes = []
for i in range(H):
    r = forest[i].astype(np.int8)
    d = np.diff(np.concatenate([[0], r, [0]]))
    starts = np.where(d == 1)[0]; ends = np.where(d == -1)[0]
    for a, b in zip(starts, ends):
        boxes.append((X(a), Y(i), X(b), Y(i+1)))
print('runs', len(boxes))
arr = np.array(boxes)
geoms = shapely.box(arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3])
u = shapely.union_all(geoms)
print('union done', round(time.time()-t, 1), u.geom_type, shapely.get_num_geometries(u), shapely.get_num_coordinates(u))
shapely.to_wkb(u)
open(f'{D}/raw/ksj/forest_union.wkb', 'wb').write(shapely.to_wkb(u))
json.dump(stats, open(f'{D}/raw/ksj/forest_stats.json', 'w'), indent=1)
