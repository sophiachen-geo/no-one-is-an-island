"""Rough placement of a sheet from gcps.json: an affine (k2), the k2 fit's linear part with a translation from two points
(k1, same print scale), or a similarity (mie22, y down). Writes E = a x + b y + c, N = d x + e y + f (x, y = raster px).
usage: init.py <sheet key> <out.npy>"""
import sys, json, numpy as np
from pyproj import Transformer
key, out = sys.argv[1:3]
G = json.load(open(__file__.replace("init.py", "gcps.json"), encoding="utf-8"))[key]
tr = Transformer.from_crs(4326, 6674, always_xy=True)
P = np.array([p["px"] for p in G["points"]], float); Q = np.array([tr.transform(*p["ll"]) for p in G["points"]])
if G["kind"] == "affine":
    A = np.c_[P, np.ones(len(P))]
    cx = np.linalg.lstsq(A, Q[:, 0], rcond=None)[0]; cy = np.linalg.lstsq(A, Q[:, 1], rcond=None)[0]
    f = np.r_[cx, cy]
elif G["kind"] == "translate":
    f2 = np.load(G["linear_from"]); L = np.array([[f2[0], f2[1]], [f2[3], f2[4]]])
    t = (Q - P @ L.T).mean(axis=0); f = np.r_[L[0, 0], L[0, 1], t[0], L[1, 0], L[1, 1], t[1]]
else:   # similarity with the image y axis pointing down: E = a x + b y + c, N = b x − a y + d
    A = np.array([[x, y, 1, 0] for x, y in P] + [[-y, x, 0, 1] for x, y in P], float)
    a, b, c, d = np.linalg.lstsq(A, np.r_[Q[:, 0], Q[:, 1]], rcond=None)[0]
    f = np.r_[a, b, c, b, -a, d]
np.save(out, f)
pred = np.c_[P @ f[0:2] + f[2], P @ f[3:5] + f[5]]
print(key, G["kind"], "residuals m", np.round(np.hypot(*(pred - Q).T), 1).tolist(), "m/px", round(float(np.hypot(f[0], f[3])), 4))
