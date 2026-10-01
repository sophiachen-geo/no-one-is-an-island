"""Kamikura micro-study, step 2: 1 m terrain grid in the page's plane, slope, the break of slope and its offset.

Reads dem1.npy / dem1.json (01_fetch.py). Writes terrain.npz (1 m grid in JGD2011 / CS VI metres: elevation,
slope, mountain mask) and terrain.json (break-of-slope line, the line 25 m upslope of it, the plain level).

Definitions (all on GSI DEM1A, bare ground, 1 m):
  plain level   median elevation of near-flat ground (slope < 3°) below 15 m in the frame
  mountain      ground at least 1 m above the plain that is either steeper than 12° or more than 3 m above the
                plain, connected to the slopes above 40 m; small spurs removed (opening, r = 2 m)
  slope break   the mountain's edge against the plain
  west boundary the line 25 m (horizontal) inside the mountain from the slope break
"""
import json, math
import numpy as np
from pyproj import Transformer
from scipy import ndimage as ndi
from skimage import measure, morphology

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
P2LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)
FRAME_LL = (135.9795, 33.7200, 135.9935, 33.7280)          # study area + transect to the city hall
OFFSET_M = 25.0


def grid_frame():
    xs, ys = LL2P.transform([FRAME_LL[0], FRAME_LL[2], FRAME_LL[0], FRAME_LL[2]], [FRAME_LL[1], FRAME_LL[1], FRAME_LL[3], FRAME_LL[3]])
    x0, x1 = math.floor(min(xs)), math.ceil(max(xs)); y0, y1 = math.floor(min(ys)), math.ceil(max(ys))
    return x0, y1, x1 - x0, y1 - y0                           # west, north, width, height (m); row 0 = north


def resample(dem, meta, x0, y1, W, H):
    """Bilinear sample of the Web-Mercator DEM tiles at the centres of a 1 m grid in CS VI."""
    n = 2 ** meta["z"]
    gx, gy = np.meshgrid(x0 + 0.5 + np.arange(W), y1 - 0.5 - np.arange(H))
    lon, lat = P2LL.transform(gx.ravel(), gy.ravel())
    lon, lat = np.asarray(lon), np.radians(np.asarray(lat))
    px = ((lon + 180) / 360 * n - meta["tx0"]) * 256 - 0.5
    py = ((1 - np.log(np.tan(lat) + 1 / np.cos(lat)) / np.pi) / 2 * n - meta["ty0"]) * 256 - 0.5
    ok = ~np.isnan(dem)
    filled = np.where(ok, dem, 0.0)
    v = ndi.map_coordinates(filled, [py, px], order=1, mode="nearest")
    w = ndi.map_coordinates(ok.astype(float), [py, px], order=1, mode="nearest")
    v = np.where(w > 0.99, v / np.maximum(w, 1e-9), np.nan)
    return v.reshape(H, W).astype(np.float32)


def lines_from_mask(mask, x0, y1):
    """Boundary polylines of a boolean mask, in CS VI metres (pixel centres)."""
    out = []
    for c in measure.find_contours(mask.astype(float), 0.5):
        if len(c) < 20: continue
        out.append([(round(x0 + 0.5 + col, 2), round(y1 - 0.5 - row, 2)) for row, col in c])
    return out


def main():
    dem = np.load("dem1.npy"); meta = json.load(open("dem1.json"))
    x0, y1, W, H = grid_frame()
    z = resample(dem, meta, x0, y1, W, H)
    zs = ndi.gaussian_filter(np.where(np.isnan(z), np.nanmedian(z), z), 1.0)
    gy, gx = np.gradient(zs)                                  # 1 m spacing; rows run south, so gy has the sign flipped (irrelevant for slope)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    flat = (slope < 3) & (zs < 15) & ~np.isnan(z)
    plain = float(np.median(zs[flat]))
    cand = (zs >= plain + 1.0) & ((slope >= 12) | (zs >= plain + 3.0))
    cand = morphology.binary_opening(cand, morphology.disk(2))
    lab, nl = ndi.label(cand)
    keep = np.unique(lab[(zs >= 40) & cand]); keep = keep[keep > 0]
    mountain = np.isin(lab, keep)
    mountain = ndi.binary_fill_holes(mountain)
    inner = ndi.distance_transform_edt(mountain)               # metres to the slope break, inside the mountain
    np.savez_compressed("terrain.npz", z=z, slope=slope, mountain=mountain, inner=inner.astype(np.float32),
                        frame=np.array([x0, y1, W, H], dtype=np.float64))
    brk = lines_from_mask(mountain, x0, y1)
    off = lines_from_mask(inner >= OFFSET_M, x0, y1)
    json.dump({"frame": [x0, y1, W, H], "plain_m": round(plain, 2), "offset_m": OFFSET_M,
               "break": brk, "offset": off, "dem_share_1m": None}, open("terrain.json", "w"))
    print(f"grid {W}×{H} m · plain {plain:.2f} m · mountain {mountain.mean():.1%} of frame · "
          f"break lines {len(brk)} ({sum(len(l) for l in brk)} pts) · offset lines {len(off)}")


if __name__ == "__main__":
    main()
