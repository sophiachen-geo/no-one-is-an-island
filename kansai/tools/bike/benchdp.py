"""Road-bed tracking on the 5 m laser DEM (Viterbi).
At every sample along the mapped line, candidate positions lie across the line at offsets -OFF..+OFF m.
Unary cost: cross-slope at the candidate (a road is a flat bench) + a small pull toward the mapped line.
Pairwise cost: sideways jumps between consecutive samples, and implied grades steeper than GMAX.
Dynamic programming picks the cheapest continuous path; its heights are the road-bed profile.
Runs only on open road: tunnels and bridges are interpolated between their ends afterwards."""
import math, numpy as np
import dem
OFF, DO = 15.0, 1.5
OFFS = np.arange(-OFF, OFF + 1e-9, DO)
LAM, ALPHA, BETA, GMAX = 0.10, 0.03, 4.0, 0.12
def _k(lat):
    return 111412.84 * math.cos(math.radians(lat)), 111132.954 - 559.822 * math.cos(2 * math.radians(lat))
def grid(pts):
    n = len(pts); J = len(OFFS)
    H = np.full((n, J), np.nan)
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
        kx, ky = _k(p[1])
        dx = (b[0] - a[0]) * kx; dy = (b[1] - a[1]) * ky; L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        for j, o in enumerate(OFFS):
            h, s = dem.sample(p[0] + nx * o / kx, p[1] + ny * o / ky)
            if h is not None: H[i, j] = h
    return H
def track(pts, H):
    n, J = H.shape
    ds = np.array([pts[i][2] - pts[i - 1][2] for i in range(1, n)])
    cs = np.full((n, J), 10.0)
    cs[:, 1:-1] = np.abs(H[:, 2:] - H[:, :-2]) / (2 * DO)
    U = np.nan_to_num(cs, nan=10.0) + LAM * np.abs(OFFS)[None, :] / OFF
    jump = ALPHA * np.abs(OFFS[:, None] - OFFS[None, :]) / DO       # [j_prev, j]
    cost = U[0].copy(); back = np.zeros((n, J), dtype=np.int32)
    for i in range(1, n):
        g = np.abs(H[i][None, :] - H[i - 1][:, None]) / max(ds[i - 1], 1e-6)
        pen = BETA * np.maximum(0.0, np.nan_to_num(g, nan=1.0) - GMAX)
        tot = cost[:, None] + jump + pen
        back[i] = np.argmin(tot, axis=0)
        cost = tot[back[i], np.arange(J)] + U[i]
    j = int(np.argmin(cost)); path = [j]
    for i in range(n - 1, 0, -1):
        j = int(back[i, j]); path.append(j)
    path = path[::-1]
    h = np.array([H[i, path[i]] for i in range(n)])
    return h, OFFS[path]
