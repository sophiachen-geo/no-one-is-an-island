"""Register a Wakayama R8 tsunami map raster (reassembled from the PDF strips) to JGD2011 / CS VI (EPSG:6674).
Start: an affine from the facility dots the map prints (city hall, fire HQ, police HQ, prefectural office).
Refine: GSI building outlines (optimal_bvmap-v1 BldA, the same 電子国土基本情報 the map's base is drawn from),
sampled every 2 m, are projected into the raster; the affine (6 parameters) is tuned so they fall on the map's
dark line work (robust mean of the distance, capped at 8 px). Reports the residual distribution.
usage: register.py <raster.png> <init_affine.npy> <out_affine.npy>
env: OBV_DIR (GSI z16 tiles, default ./obv16); CLIP_PREF + PREFS (only outlines inside that prefecture of prefs.geojson)"""
import sys, os, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.optimize import minimize
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bike"))
import town_gsi
town_gsi.D = os.environ.get("OBV_DIR", os.path.join(os.getcwd(), "obv16"))
ras, init, out = sys.argv[1:4]
im = np.asarray(Image.open(ras).convert("RGB")).astype(float)
lum = im.mean(axis=2); sat = im.max(axis=2) - im.min(axis=2)
line = (lum < 165) & (sat < 60)                       # grey/black line work, not the tinted inundation fill
dist = ndi.distance_transform_edt(~line)              # px to the nearest line pixel
H, W = dist.shape
c = np.load(init); cx, cy = c[:3], c[3:]               # E = cx·[x, y, 1], N = cy·[x, y, 1]
A = np.array([[cx[0], cx[1]], [cy[0], cy[1]]]); t = np.array([cx[2], cy[2]])
Ainv = np.linalg.inv(A)
L = town_gsi.layers(("BldA",))["BldA"]
pts = []
for g, p in L:
    ring = g.exterior
    n = max(4, int(ring.length // 2))
    for k in range(n):
        q = ring.interpolate(k * ring.length / n); pts.append((q.x, q.y))
pts = np.array(pts)
if os.environ.get("CLIP_PREF"):                      # keep only outlines inside one prefecture (Mie draws only its own land)
    import json as _j
    from shapely.geometry import shape as _shape, Point as _Pt
    from shapely.ops import transform as _tfm
    from shapely.prepared import prep as _prep
    from pyproj import Transformer as _T
    _poly = _prep(_tfm(_T.from_crs(4326, 6674, always_xy=True).transform,
                       _shape(_j.load(open(os.environ.get("PREFS", "prefs.geojson")))[os.environ["CLIP_PREF"]])))
    pts = np.array([q for q in pts if _poly.contains(_Pt(q[0], q[1]))])
# keep the points that fall inside the raster under the initial transform
px = (pts - t) @ Ainv.T
keep = (px[:, 0] > 5) & (px[:, 0] < W - 6) & (px[:, 1] > 5) & (px[:, 1] < H - 6)
pts = pts[keep]
print("building outline samples", len(pts), file=sys.stderr)
def to_px(theta):
    a, b, c_, d, e, f = theta                           # inverse affine: x = a E + b N + c ; y = d E + e N + f
    x = a * pts[:, 0] + b * pts[:, 1] + c_; y = d * pts[:, 0] + e * pts[:, 1] + f
    return x, y
def cost(theta, cap=8.0):
    x, y = to_px(theta)
    v = ndi.map_coordinates(dist, [y, x], order=1, mode="nearest")
    return np.minimum(v, cap).mean()
theta0 = np.r_[Ainv[0], -(Ainv[0] @ t), Ainv[1], -(Ainv[1] @ t)]
theta0 = np.array([theta0[0], theta0[1], theta0[2], theta0[3], theta0[4], theta0[5]])
print("cost at start", round(cost(theta0), 3), file=sys.stderr)
best = theta0
for cap in (8.0, 4.0, 2.5):
    # scale the parameters so the optimiser steps are comparable (metres vs. px)
    s = np.array([1e-3, 1e-3, 1.0, 1e-3, 1e-3, 1.0])
    r = minimize(lambda u: cost(best + u * s, cap), np.zeros(6), method="Powell", options={"xtol": 1e-4, "ftol": 1e-6, "maxiter": 20000})
    best = best + r.x * s
    print("cap", cap, "cost", round(r.fun, 3), file=sys.stderr)
x, y = to_px(best)
v = ndi.map_coordinates(dist, [y, x], order=1, mode="nearest")
# back to the forward affine (pixel -> metres)
Ai = np.array([[best[0], best[1]], [best[3], best[4]]]); ti = np.array([best[2], best[5]])
Af = np.linalg.inv(Ai); tf = -Af @ ti
fwd = np.r_[Af[0, 0], Af[0, 1], tf[0], Af[1, 0], Af[1, 1], tf[1]]
np.save(out, fwd)
sx = np.hypot(Af[0, 0], Af[1, 0]); sy = np.hypot(Af[0, 1], Af[1, 1])
print(json.dumps({"samples": int(len(pts)), "median_px": round(float(np.median(v)), 2), "p75_px": round(float(np.percentile(v, 75)), 2),
                  "share_within_1px": round(float((v <= 1).mean()), 3), "share_within_2px": round(float((v <= 2).mean()), 3),
                  "m_per_px": [round(float(sx), 4), round(float(sy), 4)], "rot_deg": round(float(np.degrees(np.arctan2(Af[1, 0], Af[0, 0]))), 3),
                  "skew_deg": round(float(np.degrees(np.arctan2(Af[0, 1], Af[1, 1]) + 0)), 3)}))
