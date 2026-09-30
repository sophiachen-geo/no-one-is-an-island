"""Long profile of the Totsukawa-Kumano main stem (D8 path on 3" SRTM) + valley-wall envelope,
plus the coastal chain south of the mouth. Output: profile.json"""
import json, math, numpy as np
from scipy.ndimage import maximum_filter, gaussian_filter
g = json.load(open("grid3.json")); H, W, res = g["H"], g["W"], g["res"]
dem = np.load("dem3.npy"); par = np.load("par3.npy").ravel(); acc = np.load("acc3.npy")
def rc(lat, lon): return int(round((35.0 - lat) / res)), int(round((lon - 135.0) / res))
def ll(i): r, c = divmod(i, W); return 35.0 - r * res, 135.0 + c * res
def hav(a, b):
    R = 6371.0; la1, lo1 = map(math.radians, a); la2, lo2 = map(math.radians, b)
    return 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
# source: highest-accumulation-weighted path start near the Dorogawa headwaters of the Ten-no-kawa
r0, c0 = rc(34.262, 135.892)
win = acc[r0 - 15:r0 + 15, c0 - 15:c0 + 15]
k = np.unravel_index(np.argmax(win), win.shape); start = (r0 - 15 + k[0]) * W + (c0 - 15 + k[1])
path = [start]
while par[path[-1]] >= 0 and len(path) < 20000:
    nxt = par[path[-1]]
    r, c = divmod(nxt, W)
    path.append(nxt)
    pass
pts = [ll(i) for i in path]
d = [0.0]
for a, b in zip(pts, pts[1:]): d.append(d[-1] + hav(a, b))
elev = np.array([dem[divmod(i, W)] for i in path], dtype=float)
elev = np.minimum.accumulate(elev)            # river bed never climbs downstream
env_grid = maximum_filter(gaussian_filter(dem, 1.0), size=61)   # ~2.8 km half-window
env = gaussian_filter(np.array([env_grid[divmod(i, W)] for i in path], dtype=float), 6)
L = d[-1]
print("river path km", round(L, 1), "cells", len(path), "end", pts[-1])
def at(lat, lon):
    j = min(range(len(pts)), key=lambda i: hav(pts[i], (lat, lon)))
    return round(d[j], 1), round(hav(pts[j], (lat, lon)), 2)
marks = {k: at(*v) for k, v in {
    "tenkawa": (34.2419, 135.8553), "totsukawa": (33.9885, 135.7925), "hongu": (33.8382, 135.7731),
    "hitari": (33.8052, 135.8707), "miyai": (33.793, 135.905), "takata_conf": (33.7445, 135.935), "shingu": (33.7241, 135.9925),
    "kazeya": (34.0444, 135.7881), "futatsuno": (33.9092, 135.7829), "saruya": (34.1793, 135.7413)}.items()}
print(marks)
# downsample
idx = np.linspace(0, len(path) - 1, 320).astype(int)
prof = [[round(d[i], 2), round(float(elev[i]), 1), round(float(env[i]), 1)] for i in idx]
# coastal chain south of the mouth (straight-line cumulative distance between places)
coast = [("shingu", 33.7241, 135.9925), ("miwasaki", 33.6894, 135.9848), ("ukui", 33.6625, 135.9723), ("nachikatsuura", 33.6281, 135.9416),
         ("taiji", 33.5941, 135.9439), ("koza", 33.5193, 135.8209), ("kushimoto", 33.4756, 135.7817)]
cd = [0.0]
for a, b in zip(coast, coast[1:]): cd.append(cd[-1] + hav(a[1:], b[1:]))
json.dump({"river_km": round(L, 1), "profile": prof, "marks": marks, "coast": [[c[0], round(x, 1)] for c, x in zip(coast, cd)]}, open("profile.json", "w"))
print("coast", [(c[0], round(x, 1)) for c, x in zip(coast, cd)])
