"""Classify a registered tsunami map raster into its depth classes (Wakayama R8: seven; LEGEND=mie: Mie 2026, eight) and
resample to a 1 m grid in JGD2011 / CS VI (EPSG:6674).

Class colours are the legend's own fills, read from the PDF's vector drawing (pymupdf get_drawings):
  1 0.01–0.3 m (255,255,179) · 2 0.3–0.5 m (247,245,169) · 3 0.5–1 m (248,225,166) · 4 1–3 m (255,216,192)
  5 3–5 m (255,183,183) · 6 5–10 m (255,145,145) · 7 10–20 m (242,133,201)
A pixel takes the nearest legend colour within RGB distance 22 (JPEG noise; the class means in the rasters sit within
5 of the legend). The base map's grey line work and printed labels cover the fill in places: unclassified pixels are
filled by the most frequent class among their classified neighbours (5×5, three passes), then a 3×3 majority filter
removes JPEG speckle at class edges. The grid cell takes the class at its centre through the sheet's quadratic
registration (r8_poly.py).
usage: classify.py <raster.png> <poly.npz> <aff.npy> <out.npz>"""
import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
ras, polyf, afff, out = sys.argv[1:5]
LEG = np.array([(255, 255, 179), (247, 245, 169), (248, 225, 166), (255, 216, 192), (255, 183, 183), (255, 145, 145), (242, 133, 201)], float)
import os
if os.environ.get("LEGEND") == "mie":                 # Mie adds an eighth class, 20 m and over
    LEG = np.vstack([LEG, (220, 122, 220)])
NC = len(LEG)
im = np.asarray(Image.open(ras).convert("RGB")).astype(float)
H, W, _ = im.shape
lum = im.mean(axis=2); sat = im.max(axis=2) - im.min(axis=2)
cls = np.zeros((H, W), np.uint8)
cand = (sat >= 10) & (lum > 140)
idx = np.nonzero(cand)
px = im[idx]
d = np.linalg.norm(px[:, None, :] - LEG[None, :, :], axis=2)
k = d.argmin(1); ok = d.min(1) < 22
cls[idx[0][ok], idx[1][ok]] = (k[ok] + 1).astype(np.uint8)
raw = cls.copy()
def mode_fill(c, size=5, min_n=6):
    out = c.copy()
    counts = np.stack([ndi.uniform_filter((c == j).astype(np.float32), size) * size * size for j in range(1, NC + 1)])
    best = counts.argmax(0) + 1; nbest = counts.max(0)
    fill = (c == 0) & (nbest >= min_n)
    out[fill] = best[fill]
    return out
for _ in range(3):
    cls = mode_fill(cls)
# dense blocks: grey outlines leave few fill pixels and the JPEG bleeds their colour. A pixel still unclassified counts
# as inundated when it is faintly tinted (ink beyond its grey part, not the dark road band) or is line work, inside the
# envelope of the classified area (closing over 5 px, holes filled); it takes the class of the nearest classified pixel
# within 8 px.
ink = 255.0 - im; neutral = ink.min(axis=2); chroma = np.linalg.norm(ink - neutral[..., None], axis=2)
tinted = (chroma > 10) & (neutral < 60)
envelope = ndi.binary_fill_holes(ndi.binary_closing(cls > 0, structure=np.ones((3, 3)), iterations=5))
dist_c, (iy, ix) = ndi.distance_transform_edt(cls == 0, return_indices=True)
grow = (cls == 0) & envelope & ((tinted) | (lum < 200)) & (dist_c <= 8)
cls[grow] = cls[iy[grow], ix[grow]]
# 3×3 majority among classified pixels (keeps 0 where nothing is classified)
counts = np.stack([ndi.uniform_filter((cls == j).astype(np.float32), 3) * 9 for j in range(1, NC + 1)])
maj = (counts.argmax(0) + 1).astype(np.uint8)
cls = np.where((cls > 0) & (counts.max(0) >= 5), maj, cls)
# resample to a 1 m grid in EPSG:6674 over the sheet's footprint
P = np.load(polyf); th, c0, sc = P["th"], P["c0"], float(P["sc"])
f = np.load(afff)
corners = np.array([[0, 0], [W, 0], [0, H], [W, H]], float)
E = f[0] * corners[:, 0] + f[1] * corners[:, 1] + f[2]; N = f[3] * corners[:, 0] + f[4] * corners[:, 1] + f[5]
e0, e1 = np.floor(E.min()) - 40, np.ceil(E.max()) + 40; n0, n1 = np.floor(N.min()) - 40, np.ceil(N.max()) + 40
ee = np.arange(e0 + 0.5, e1, 1.0); nn = np.arange(n1 - 0.5, n0, -1.0)      # rows run north → south
grid = np.zeros((len(nn), len(ee)), np.uint8); inside = np.zeros_like(grid, bool)
for r0 in range(0, len(nn), 512):
    NN, EE = np.meshgrid(nn[r0:r0 + 512], ee, indexing="ij")
    u = (EE - c0[0]) / sc; v = (NN - c0[1]) / sc
    B = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], -1)
    x = B @ th[:6]; y = B @ th[6:]
    xi = np.rint(x).astype(int); yi = np.rint(y).astype(int)
    m = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    g = np.zeros(xi.shape, np.uint8); g[m] = cls[yi[m], xi[m]]
    grid[r0:r0 + 512] = g; inside[r0:r0 + 512] = m
np.savez_compressed(out, grid=grid, inside=inside, e0=e0, n1=n1)
area = {int(j): int((grid == j).sum()) for j in range(1, NC + 1)}
print(json.dumps({"raster": ras, "classified_px": int((raw > 0).sum()), "after_fill_px": int((cls > 0).sum()),
                  "grid": [int(grid.shape[0]), int(grid.shape[1])], "class_m2": area, "inundated_ha": round(sum(area.values()) / 1e4, 1),
                  "top_row_px": int((cls[:3] > 0).sum())}))
