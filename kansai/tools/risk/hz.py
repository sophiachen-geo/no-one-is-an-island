"""Shared inputs of the risk analysis (EPSG:6674): the 2026 tsunami depth grids, arrival times from Wakayama's animation,
ground heights (GSI DEM5A mosaic of the main build; DEM5B/5C/10B per point where 5A is missing, cached in ./dem_tiles),
municipal boundaries (N03, 1 January 2026)."""
import json, math, os, sys
import numpy as np
import cfg
from shapely.geometry import shape
from shapely.ops import unary_union, transform as tfm
from shapely.prepared import prep
from pyproj import Transformer
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
TI = Transformer.from_crs(6674, 4326, always_xy=True).transform
def _muni(fn, name):
    d = json.load(open(fn, encoding="utf-8"))
    return tfm(TR, unary_union([shape(f["geometry"]) for f in d["features"] if f["properties"].get("N03_004") == name]))
SH = _muni(cfg.geo("ksj", "N03-20260101_30.geojson"), "新宮市")
KI = _muni(cfg.geo("ksj", "N03-20260101_24.geojson"), "紀宝町")
SHp, KIp = prep(SH), prep(KI)
# 2026 tsunami depth classes (1 m grids). Wakayama R8: 1 0.01–0.3, 2 0.3–0.5, 3 0.5–1, 4 1–3, 5 3–5, 6 5–10, 7 10–20 m;
# Mie 2026 adds 8: 20 m and over.
CLS_LO = np.array([0, 0.01, 0.3, 0.5, 1, 3, 5, 10, 20.0]); CLS_HI = np.array([0, 0.3, 0.5, 1, 3, 5, 10, 20, 30.0])
_K = np.load(cfg.t26("r8_k_grid.npz")); _S3 = np.load(cfg.t26("r8_s_grid.npz")); _M = np.load(cfg.t26("cls_mie22.npz"))
GRIDS = {"wk_max": (_K["grid"], float(_K["e0"]), float(_K["n1"])), "wk_freq": (_S3["grid"], float(_S3["e0"]), float(_S3["n1"])),
         "mie_max": (_M["grid"], float(_M["e0"]), float(_M["n1"]))}
def grid_at(name, x, y):
    g, e0, n1 = GRIDS[name]
    c = np.floor(np.asarray(x) - e0).astype(int); r = np.floor(n1 - np.asarray(y)).astype(int)
    ok = (r >= 0) & (r < g.shape[0]) & (c >= 0) & (c < g.shape[1])
    out = np.zeros(np.shape(x), np.uint8); out[ok] = g[r[ok], c[ok]]
    return out
def muni_of(x, y):
    from shapely.geometry import Point
    return np.array([1 if SHp.contains(Point(a, b)) else (2 if KIp.contains(Point(a, b)) else 0) for a, b in zip(np.ravel(x), np.ravel(y))])
def tsunami_max(x, y, muni):
    """2026 maximum-class depth class: Wakayama R8 in Shingū, Mie 2026 in Kihō (0 = dry or other municipality)."""
    a = grid_at("wk_max", x, y); b = grid_at("mie_max", x, y)
    return np.where(muni == 1, a, np.where(muni == 2, b, 0)).astype(np.uint8)
def tsunami_freq(x, y, muni):
    """2026 frequent class (Wakayama R8 3連動) in Shingū; Kihō has no published L1 map (255 = unknown)."""
    a = grid_at("wk_freq", x, y)
    return np.where(muni == 1, a, np.where(muni == 2, 255, 0)).astype(np.uint8)
# arrival: first frame drawn wet in Wakayama's R8 2D animations (1 frame = 10 s); panel px -> EPSG:6674 affine
_A = np.load(cfg.t26("aff_kyodai_adj.npy"))
_Ainv = np.linalg.inv(np.array([[_A[0], _A[1]], [_A[3], _A[4]]]))
_VID = {k: np.load(cfg.t26(f"{k}.npz")) for k in ("kyodai", "sanren")}
def arrival(which, x, y, search_px=2):
    """Minutes from the earthquake to the first wetting (≈1 cm) at (x, y); NaN outside the animation or never wet.
    A point drawn dry takes the earliest wet land pixel within search_px pixels (the map and the animation differ at
    the edges by about one pixel)."""
    Z = _VID[which]; first = Z["first"]; w0 = Z["water0"]
    h, w = first.shape
    d = np.stack([np.asarray(x) - _A[2], np.asarray(y) - _A[5]])
    px, py = _Ainv @ d.reshape(2, -1)
    out = np.full(px.shape, np.nan)
    land_first = np.where((first >= 0) & ~w0, first, 10 ** 6)
    from scipy import ndimage as ndi
    k = 2 * search_px + 1
    mn = ndi.minimum_filter(land_first, size=k, mode="constant", cval=10 ** 6)
    xi = np.floor(px).astype(int); yi = np.floor(py).astype(int)
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    v = np.full(px.shape, 10 ** 6)
    v[ok] = np.where(land_first[yi[ok], xi[ok]] < 10 ** 6, land_first[yi[ok], xi[ok]], mn[yi[ok], xi[ok]])
    # a point drawn as water from the first frame (low ground wetted by subsidence) arrives at 0
    wz = np.zeros(px.shape, bool); wz[ok] = w0[yi[ok], xi[ok]]
    out[ok & (v < 10 ** 6)] = v[ok & (v < 10 ** 6)] * 10 / 60
    out[ok & wz & ~(v < 10 ** 6)] = 0.0
    out[~ok] = np.nan
    return out.reshape(np.shape(x)), ok.reshape(np.shape(x))
# ground height: GSI DEM5A mosaic (z15 web-mercator pixels), then DEM5B/5C/10B per point where 5A is missing
_dem = np.load(cfg.geo("gsi_dem5.npy")); _dm = json.load(open(cfg.geo("gsi_dem5.json")))
sys.path.insert(0, cfg.BIKE)
def ground(x, y):
    from scipy import ndimage as ndi
    lon, lat = TI(np.asarray(x, float), np.asarray(y, float))
    n = 2 ** _dm["z"]
    X = ((lon + 180) / 360 * n - _dm["tx0"]) * 256 - 0.5
    Y = ((1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n - _dm["ty0"]) * 256 - 0.5
    v = ndi.map_coordinates(np.nan_to_num(_dem, nan=-9999), [np.ravel(Y), np.ravel(X)], order=1, cval=-9999)
    bad = ndi.map_coordinates(np.isnan(_dem).astype(float), [np.ravel(Y), np.ravel(X)], order=1, cval=1) > 0
    v = v.astype(float); v[bad] = np.nan
    if bad.any():
        import dem
        lo, la = np.ravel(lon), np.ravel(lat)
        for i in np.nonzero(bad)[0]:
            r = dem.sample(float(lo[i]), float(la[i]))
            v[i] = r[0] if r and r[0] is not None else np.nan
    return v.reshape(np.shape(x))
