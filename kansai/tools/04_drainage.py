"""Priority-flood depression filling + D8 flow directions on the 3" grid, seeded from the OSM sea mask
(so the flattened lower river is not mistaken for sea). Writes par3.npy (downstream neighbour) and acc3.npy."""
import numpy as np, heapq, time, json, shapely
from shapely.geometry import shape
g = json.load(open("grid3.json")); H, W, res = g["H"], g["W"], g["res"]
d3 = np.load("dem3.npy")
L = shape(json.load(open("land.geojson"))).simplify(0.0003)
S, Wl, N, E = 33.38, 135.25, 34.45, 136.42
lats = 35.0 - (np.arange(H) + 0.5) * res   # approx cell centres
lons = 135.0 + (np.arange(W) + 0.5) * res
t0 = time.time()
sea = d3 <= 0.5
r_in = np.where((lats >= S) & (lats <= N))[0]; c_in = np.where((lons >= Wl) & (lons <= E))[0]
LON, LAT = np.meshgrid(lons[c_in], lats[r_in])
inside = shapely.contains_xy(L, LON.ravel(), LAT.ravel()).reshape(LON.shape)
sea[np.ix_(r_in, c_in)] = ~inside
print("mask", time.time() - t0, "land cells in bbox", inside.sum())
np.save("sea3.npy", sea)
elev = d3.ravel().tolist(); seaf = sea.ravel()
Nn = H * W
parent = [-1] * Nn; seen = bytearray(Nn); order = []; pq = []
for i in np.where(seaf)[0].tolist():
    seen[i] = 1; pq.append((elev[i] if elev[i] < 0 else 0.0, i))
for r in (0, H - 1):
    for c in range(W):
        i = r * W + c
        if not seen[i]: seen[i] = 1; pq.append((elev[i], i))
for c in (0, W - 1):
    for r in range(H):
        i = r * W + c
        if not seen[i]: seen[i] = 1; pq.append((elev[i], i))
heapq.heapify(pq)
nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
while pq:
    e, i = heapq.heappop(pq)
    order.append(i)
    r, c = divmod(i, W)
    for dr, dc in nb:
        rr, cc = r + dr, c + dc
        if 0 <= rr < H and 0 <= cc < W:
            j = rr * W + cc
            if not seen[j]:
                seen[j] = 1
                fj = elev[j] if elev[j] > e else e + 1e-4
                parent[j] = i
                heapq.heappush(pq, (fj, j))
print("flood", time.time() - t0)
par = np.array(parent, dtype=np.int64); acc = np.ones(Nn)
for i in reversed(order):
    p = par[i]
    if p >= 0: acc[p] += acc[i]
np.save("acc3.npy", acc.reshape(H, W)); np.save("par3.npy", par.reshape(H, W))
print("done", time.time() - t0)
