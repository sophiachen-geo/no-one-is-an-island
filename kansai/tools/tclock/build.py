"""The tsunami clock of the Kansai page: when Wakayama's 2026 animation first draws each place wet, minute by minute.

    python3 kansai/tools/tclock/build.py <kyodai.npz> <aff_kyodai_adj.npy> <kansai/index.html> <kansai/data/tclock.js>

Inputs come from kansai/tools/tsunami2026 (see its README): vid_decode.py gives, per pixel of the animation's map panel
(9.4 m), the first frame drawn wet three frames running (1 frame = 10 s); vid_register.py and vid_shift.py give the panel
pixel → EPSG:6674 affine. Every pixel first drawn wet after frame 0 falls in a one-minute band (0–1, 1–2, … 59–60 minutes
after the earthquake); each band is traced as polygons (pixel outlines), simplified by a third of a pixel and written in the
page's coordinates (1 unit = 100 m from the GEO origin). Left out: ground drawn wet from frame 0 (sea, river, low ground
lowered by the earthquake), water arriving after the first hour, and the panel's frame line (its outermost pixels).

Output: window.__TCLOCK = {"minutes": 60, "bands": [[minute, "svg path"], …], "share": {minute: share of the hour's wet
ground already wet}} — the shares are for checks, the page draws only the bands."""
import sys, json, re
import numpy as np
from skimage import measure
from shapely.geometry import LineString

NPZ, AFF, PAGE, OUT = sys.argv[1:5]
Z = np.load(NPZ); first = Z["first"].astype(int); w0 = Z["water0"]; A = np.load(AFF)
g = json.loads(re.search(r"/\*GEO:BEGIN\*/(.*?)/\*GEO:END\*/", open(PAGE, encoding="utf-8").read(), re.S).group(1))
X0, Y1 = g["origin"]
MIN = 60
minute = np.where((first >= 0) & ~w0, np.ceil(first * 10 / 60.0), 0).astype(int)   # 0 = never (or from the start)
minute[minute == 0] = 0
minute[(first == 0) & ~w0] = 1                                                    # wet in the first seconds: the first minute
# the panel's outermost row and column are its frame line: never drawn as water at frame 0, though the pixels inside are sea
# along the bottom and right edges, and the decoder reads its colour shifts as wetting the next pixel in does not show
# (on the top, bottom and right edges 20, 3 and 2 of its 83, 354 and 542 "wet" pixels agree with their neighbours)
minute[[0, -1], :] = 0; minute[:, [0, -1]] = 0
timed = (minute >= 1) & (minute <= MIN)


def to_page(rc):
    r, c = rc[:, 0], rc[:, 1]
    x, y = c + 0.5, r + 0.5
    E = A[0] * x + A[1] * y + A[2]; N = A[3] * x + A[4] * y + A[5]
    return np.column_stack([(E - X0) / 100.0, (Y1 - N) / 100.0])


bands, npts = [], 0
for m in range(1, MIN + 1):
    mask = np.pad(minute == m, 1)
    if not mask.any():
        continue
    parts = []
    for cnt in measure.find_contours(mask.astype(float), 0.5):
        cnt = cnt - 1                                            # undo the padding
        ls = LineString(cnt).simplify(0.33, preserve_topology=False)
        pts = np.asarray(ls.coords)
        if len(pts) < 3:
            continue
        P = to_page(pts); npts += len(P)
        parts.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in P[:-1]) + "Z")
    bands.append([m, "".join(parts)])

tot = timed.sum()
share = {m: round(float(((minute >= 1) & (minute <= m)).sum() / tot), 4) for m in (5, 10, 15, 20, 30, 45, 60)}
data = {"minutes": MIN, "px_m": 9.4, "bands": bands, "share": share}
js = "window.__TCLOCK = " + json.dumps(data, separators=(",", ":")) + ";\n"
open(OUT, "w", encoding="utf-8").write(js)
print(f"{len(bands)} bands, {npts} points, {len(js) / 1024:.0f} KB; timed pixels {tot}; share wet by minute: {share}")
