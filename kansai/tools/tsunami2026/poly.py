"""Second-order polynomial refinement of a sheet registration (map metres -> pixel), from the affine of register.py:
the same building-outline fit with x, y = quadratic in (E, N). Reports residuals by ninths of the sheet.
usage: poly.py <raster.png> <affine.npy> <out.npz>   (env as register.py)"""
import sys, os, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.optimize import minimize
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bike"))
import town_gsi
town_gsi.D = os.environ.get("OBV_DIR", os.path.join(os.getcwd(), "obv16"))
ras, aff, out = sys.argv[1:4]
im = np.asarray(Image.open(ras).convert("RGB")).astype(float)
lum = im.mean(axis=2); sat = im.max(axis=2) - im.min(axis=2)
dist = ndi.distance_transform_edt(~((lum < 165) & (sat < 60))); H, W = dist.shape
f = np.load(aff); Af = np.array([[f[0], f[1]], [f[3], f[4]]]); tf = np.array([f[2], f[5]]); Ai = np.linalg.inv(Af)
L = town_gsi.layers(("BldA",))["BldA"]; pts = []
for g, p in L:
    r = g.exterior; n = max(4, int(r.length // 2))
    for k in range(n): q = r.interpolate(k * r.length / n); pts.append((q.x, q.y))
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
px0 = (pts - tf) @ Ai.T
ok = (px0[:, 0] > 5) & (px0[:, 0] < W - 6) & (px0[:, 1] > 5) & (px0[:, 1] < H - 6); pts = pts[ok]; px0 = px0[ok]
c0 = pts.mean(axis=0); sc = 2000.0
u = (pts[:, 0] - c0[0]) / sc; v = (pts[:, 1] - c0[1]) / sc        # normalised metres
B = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
# start: least squares of the affine pixel positions on the basis
bx = np.linalg.lstsq(B, px0[:, 0], rcond=None)[0]; by = np.linalg.lstsq(B, px0[:, 1], rcond=None)[0]
def cost(th, cap):
    x = B @ th[:6]; y = B @ th[6:]
    d = ndi.map_coordinates(dist, [y, x], order=1, mode="nearest"); return np.minimum(d, cap).mean()
th = np.r_[bx, by]; print("start", round(cost(th, 2.5), 4), file=sys.stderr)
for cap in (4.0, 2.5):
    s = np.r_[1, 10, 10, 10, 10, 10, 1, 10, 10, 10, 10, 10] * 0.1
    r = minimize(lambda z: cost(th + z * s, cap), np.zeros(12), method="Powell", options={"xtol": 1e-4, "ftol": 1e-7, "maxiter": 40000})
    th = th + r.x * s; print("cap", cap, round(r.fun, 4), file=sys.stderr)
x = B @ th[:6]; y = B @ th[6:]; d = ndi.map_coordinates(dist, [y, x], order=1, mode="nearest")
np.savez(out, th=th, c0=c0, sc=sc)
xs = np.quantile(x, [0, 1/3, 2/3, 1]); ys = np.quantile(y, [0, 1/3, 2/3, 1]); zones = []
for i in range(3):
    for j in range(3):
        m = (x >= xs[j]) & (x <= xs[j + 1]) & (y >= ys[i]) & (y <= ys[i + 1]); zones.append(round(float(np.median(d[m])), 2))
# how far the polynomial moves points relative to the affine (metres)
dx = (x - px0[:, 0]) * 1.314; dy = (y - px0[:, 1]) * 1.314
print(json.dumps({"median_px": round(float(np.median(d)), 3), "within_2px": round(float((d <= 2).mean()), 3), "zones_median_px": zones,
                  "shift_vs_affine_m": {"median": round(float(np.median(np.hypot(dx, dy))), 2), "max": round(float(np.max(np.hypot(dx, dy))), 2)}}))
