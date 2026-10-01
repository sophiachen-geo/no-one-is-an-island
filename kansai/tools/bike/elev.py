"""Road-bed heights from the DEM.
A mapped centreline can sit a few metres off the real road; on a 40 degree slope that is a few metres of
height per metre of offset. A road on a hillside is a bench: across the road the ground is nearly flat.
So at each sample we look across the line (+-OFF m, every DS m), find the flattest spot (smallest
cross-slope, lightly penalised by its distance from the line) and take the height there."""
import math
import dem
OFF, DS, LAM = 12.0, 2.0, 0.004    # search half-width (m), step (m), penalty per m of offset (slope units)
def _local_xy(lat):
    ky = 111132.954 - 559.822 * math.cos(2 * math.radians(lat))
    kx = 111412.84 * math.cos(math.radians(lat))
    return kx, ky
def bench(lon, lat, tlon, tlat):
    """tlon, tlat: unit tangent in degrees-per-metre already scaled; returns (h, offset_m, src)."""
    kx, ky = _local_xy(lat)
    # normal in metres → degrees
    nx, ny = -tlat, tlon
    offs = [i * DS for i in range(-int(OFF / DS), int(OFF / DS) + 1)]
    hs = []
    src = None
    for o in offs:
        h, s = dem.sample(lon + nx * o / kx, lat + ny * o / ky)
        hs.append(h)
        if o == 0: src = s
    best = None
    for i in range(1, len(offs) - 1):
        if hs[i - 1] is None or hs[i + 1] is None or hs[i] is None: continue
        cs = abs(hs[i + 1] - hs[i - 1]) / (2 * DS)
        score = cs + LAM * abs(offs[i])
        if best is None or score < best[0]: best = (score, hs[i], offs[i])
    if best is None:
        return hs[len(offs) // 2], 0.0, src
    return best[1], best[2], src
def profile(pts):
    """pts: list of (lon, lat, cum_m, ...). Returns raw and bench heights."""
    raw, ben, off, srcs = [], [], [], []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
        kx, ky = _local_xy(p[1])
        dx = (b[0] - a[0]) * kx; dy = (b[1] - a[1]) * ky; L = math.hypot(dx, dy) or 1.0
        h0, s = dem.sample(p[0], p[1])
        hb, o, _ = bench(p[0], p[1], dx / L, dy / L)
        raw.append(h0); ben.append(hb); off.append(o); srcs.append(s)
    return raw, ben, off, srcs
def median_filter(h, k=2):
    out = []
    for i in range(len(h)):
        w = sorted(x for x in h[max(0, i - k): i + k + 1] if x is not None)
        out.append(w[len(w) // 2] if w else None)
    return out
