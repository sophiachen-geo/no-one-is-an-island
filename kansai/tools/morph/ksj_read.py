# Read L03-b-21 dbfs, build a land-use raster for the frame (100 m mesh grid), save as npz
import shapefile, numpy as np, time, sys
from collections import Counter
D = sys.argv[1]
W, S, E, N = 135.25, 33.38, 136.42, 34.45
# grid units: lat 1/1200 deg, lon 1/800 deg (offset 100 deg)
lat0 = int(np.floor(S*1200)); lat1 = int(np.ceil(N*1200))
lon0 = int(np.floor((W-100)*800)); lon1 = int(np.ceil((E-100)*800))
H, Wd = lat1-lat0, lon1-lon0
print('grid', H, Wd, lat0, lon0)
grid = np.zeros((H, Wd), dtype=np.int16)  # 0 = no data
counts = Counter(); dates = Counter()
t = time.time()
for m in ['5035','5036','5135','5136']:
    r = shapefile.Reader(f'{D}/raw/ksj/L03-b-21_{m}')
    n = 0
    # check geometry of first record against code
    rec0 = r.record(0); shp0 = r.shape(0)
    for rec in r.iterRecords():
        code, lu, dt = rec[0], rec[1], rec[2]
        p, q, rr, s, tt, u, v, w = int(code[0:2]), int(code[2:4]), int(code[4]), int(code[5]), int(code[6]), int(code[7]), int(code[8]), int(code[9])
        la = p*800 + rr*100 + tt*10 + v
        lo = q*800 + s*100 + u*10 + w
        counts[(m, lu)] += 1; dates[dt[:4]] += 1
        i = la - lat0; j = lo - lon0
        if 0 <= i < H and 0 <= j < Wd:
            grid[i, j] = int(lu) if lu.strip() else -1
        n += 1
    c = rec0[0]
    la = int(c[0:2])*800 + int(c[4])*100 + int(c[6])*10 + int(c[8]); lo = int(c[2:4])*800 + int(c[5])*100 + int(c[7])*10 + int(c[9])
    print(m, n, 'check SW', (lo/800+100, la/1200), 'shape bbox', shp0.bbox, round(time.time()-t,1))
np.savez_compressed(f'{D}/raw/ksj/landuse_grid.npz', grid=grid, lat0=lat0, lon0=lon0)
print(sorted(Counter(grid.ravel().tolist()).items()))
print(sorted(counts.items()))
print(sorted(dates.items()))
