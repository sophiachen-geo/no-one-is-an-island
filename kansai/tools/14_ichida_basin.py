"""Digitise the official Ichida-gawa basin boundary (流域界) from MLIT's printed basin map.

Source: MLIT 市田川流域大規模浸水対策計画 (2019), p. 9, 図-1.2 市田川流域図 (downloaded by 01_fetch.sh to
ichida/shiryou.pdf). The green boundary line is extracted by colour, gaps are bridged between skeleton
end points, the enclosed area is filled from a seed inside the basin, and the outline is georeferenced
with an affine fit through six control points read off the map (city hall, station, schools, the sluice).

Writes ichida/ichida_basin.json. The result covers ≈5.85 km² against the official 5.36 km²; the page
quotes the official figure (see kansai/CAVEATS.md).
"""
import json
import numpy as np
import pymupdf as fitz
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import Polygon, mapping
from shapely.ops import transform
from skimage import draw, measure, morphology

DPI = 150; S = DPI / 72; ox, oy = 90, 150          # clip window on the page, PDF points
page = fitz.open("ichida/shiryou.pdf")[8]
pix = page.get_pixmap(dpi=DPI, clip=fitz.Rect(90, 150, 510, 560))
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].astype(int)
R, G, B = img[..., 0], img[..., 1], img[..., 2]
green = (R < 70) & (G > 150) & (G < 215) & (B < 70)
green[70:101, 615:792] = False                     # mask the "市田川流域界" legend text only
green = morphology.remove_small_objects(ndimage.binary_closing(green, iterations=1), 30)

# bridge the dashes: join each skeleton end point to the nearest end of another piece (≤ 70 px)
sk = morphology.skeletonize(green)
nb = ndimage.convolve(sk.astype(int), np.ones((3, 3), int), mode="constant") - 1
ends = np.argwhere(sk & (nb == 1))
lab, _ = ndimage.label(sk, structure=np.ones((3, 3)))
ring, used = green.copy(), set()
for i, (r, c) in enumerate(ends):
    best, bd = None, 1e9
    for j, (r2, c2) in enumerate(ends):
        if j == i or lab[r2, c2] == lab[r, c]:
            continue
        dd = (r - r2) ** 2 + (c - c2) ** 2
        if dd < bd:
            best, bd = j, dd
    key = (min(i, best), max(i, best)) if best is not None else None
    if best is not None and bd ** 0.5 < 70 and key not in used:
        used.add(key); rr, cc = draw.line(int(r), int(c), int(ends[best][0]), int(ends[best][1])); ring[rr, cc] = True
ring = ndimage.binary_dilation(ring, iterations=2)
filled = ndimage.binary_fill_holes(ring)
sr, sc = int((247.26 - oy) * S), int((310.11 - ox) * S)   # seed: the city hall symbol
lab2, _ = ndimage.label(filled); comp = lab2 == lab2[sr, sc]
assert lab2[sr, sc] and comp.mean() < 0.9, "boundary did not close"

# georeference: PDF points → EPSG:6674 by least squares through six control points
CP = [((310.11, 247.26), (135.99249, 33.72412)), ((328.2, 241.74), (135.99408, 33.72508)), ((275.01, 307.92), (135.98928, 33.71953)),
      ((380.49, 355.8), (135.99913, 33.71568)), ((289.05, 497.43), (135.99030, 33.70417)), ((475.11, 245.7), (136.00870, 33.72390))]
TF = Transformer.from_crs(4326, 6674, always_xy=True).transform
INV = Transformer.from_crs(6674, 4326, always_xy=True).transform
A = np.array([[1, u, v] for (u, v), _ in CP]); X = np.array([TF(*ll) for _, ll in CP])
cx, *_ = np.linalg.lstsq(A, X[:, 0], rcond=None); cy, *_ = np.linalg.lstsq(A, X[:, 1], rcond=None)
c = max(measure.find_contours(np.pad(comp.astype(float), 1), 0.5), key=len)
pts = [((cc - 1) / S + ox, (rr - 1) / S + oy) for rr, cc in c]
poly = Polygon([(cx[0] + cx[1] * u + cx[2] * v, cy[0] + cy[1] * u + cy[2] * v) for u, v in pts]).buffer(0)
pc = poly.buffer(-12).simplify(5)                  # to the centre of the drawn line
res = np.hypot(A @ cx - X[:, 0], A @ cy - X[:, 1])
print("area km2", round(pc.area / 1e6, 3), "(official 5.360); control residuals m", [round(float(r), 1) for r in res])
json.dump({"ichida_basin": mapping(transform(INV, pc)), "area_km2": round(pc.area / 1e6, 3),
           "method": "official 流域界 line (MLIT 図-1.2) extracted by colour, gaps bridged between skeleton ends, georeferenced by 6 control points",
           "control_residuals_m": [round(float(r), 1) for r in res]}, open("ichida/ichida_basin.json", "w"))
