"""Inject geo.json + profile.json (+ an affine lon/lat->svg fit for label placement) into kansai/index.html."""
import json, re, sys, numpy as np
from pyproj import Transformer
import os
HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html")
g = json.load(open("geo.json")); prof = json.load(open("profile.json"))
TF = Transformer.from_crs(6668, 6674, always_xy=True).transform
# reproduce the svg origin used by build.py from the frame: pick two known points to recover (X0, Y1)
# (build.py: sx = (x - X0)/100, sy = (Y1 - y)/100); use the named point 'shingu'
lon, lat = 135.9925, 33.7241
x, y = TF(lon, lat); px, py = g["pts"]["shingu"]
X0 = x - px * 100; Y1 = y + py * 100
lons, lats = np.meshgrid(np.linspace(135.25, 136.42, 25), np.linspace(33.38, 34.45, 25))
xs, ys = TF(lons.ravel(), lats.ravel())
sxs = (np.array(xs) - X0) / 100; sys_ = (Y1 - np.array(ys)) / 100
A = np.c_[np.ones(lons.size), lons.ravel(), lats.ravel()]
ax, *_ = np.linalg.lstsq(A, sxs, rcond=None); ay, *_ = np.linalg.lstsq(A, sys_, rcond=None)
err = np.hypot(A @ ax - sxs, A @ ay - sys_).max() * 100
print("affine max error (m):", round(err, 1))
g["aff"] = [round(v, 5) for v in list(ax) + list(ay)]
# exact positions for every "@lon,lat" label key used in the page
html_src = open(HTML, encoding="utf-8").read()
at = {}
for m in set(re.findall(r'"(@[0-9.]+,[0-9.]+)"', html_src)):
    lo, la = map(float, m[1:].split(","))
    X, Y = TF(lo, la); at[m] = [round((X - X0) / 100, 2), round((Y1 - Y) / 100, 2)]
g["at"] = at
g["profile"] = prof
blob = json.dumps(g, ensure_ascii=False, separators=(",", ":"))
html = open(HTML, encoding="utf-8").read()
html2, n = re.subn(r"/\*GEO:BEGIN\*/.*?/\*GEO:END\*/", lambda m: "/*GEO:BEGIN*/" + blob + "/*GEO:END*/", html, flags=re.S)
assert n == 1, n
open(HTML, "w", encoding="utf-8").write(html2)
print("injected", round(len(blob) / 1024, 1), "KB; page", round(len(html2) / 1024, 1), "KB")
