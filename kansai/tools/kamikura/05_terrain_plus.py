"""Kamikura micro-study, step 5: which elevation product the terrain can bear, and the terrain derivatives.

Reads (work dir): dem1.npy / dem1.json / dem1_src.npy (01), terrain.npz (02), study.json (03), GSI optimal vector
tiles (../morph/raw/bvmap/z16). Fetches GSI DEM5A (5 m) for the whole frame for comparison (dem5/).
Writes terrain_plus.npz (1 m grid, same frame as terrain.npz) and terrain_audit.json.

Audit, all on the 1 m CS VI grid of step 2:
  coverage      share of cells whose value comes from DEM1A (airborne laser, 1 m) vs the DEM5A fallback
  benchmarks    DEM1A against GSI's levelling benchmark (水準点) and triangulation point (三角点) heights printed in
                the optimal vector tiles (symbol layer, ftCodes 7103 / 7102) and the 1:25,000 spot heights (7201)
  DEM5A vs 1A   differences on open, near-flat ground (agreement) and across the channel (what 5 m cannot resolve)
  buildings     share of ground under GSI building outlines: DEM1A is a bare-ground model, interpolated there

Derivatives (1 m grid):
  local relief  z minus its Gaussian-smoothed surface (σ = 8 m, about a 20 m neighbourhood): walls, terraces, the
                channel trench and road cuts stand out against the general slope
  curvature     profile and plan curvature (Zevenbergen–Thorne) of z smoothed with σ = 2.5 m, in 1/m; profile
                curvature < 0 = concave (slope easing downhill: a foot), > 0 = convex (slope steepening: a shoulder
                or a wall top). σ sets the scale: features narrower than about 5 m are not read as curvature.
"""
import glob, json, math, os, urllib.request
import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage as ndi
from shapely.geometry import Polygon, Point, shape
from shapely import prepared
import mapbox_vector_tile

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
P2LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)
UA = {"User-Agent": "no-one-is-an-island kansai research (kamikura micro-study)"}
SIG_LRM, SIG_CURV = 8.0, 2.5


def merc_px(lon, lat, z, tx0, ty0):
    n = 2 ** z; lat = np.radians(lat)
    return ((lon + 180) / 360 * n - tx0) * 256 - 0.5, ((1 - np.log(np.tan(lat) + 1 / np.cos(lat)) / np.pi) / 2 * n - ty0) * 256 - 0.5


def grid_ll(x0, y1, W, H):
    gx, gy = np.meshgrid(x0 + 0.5 + np.arange(W), y1 - 0.5 - np.arange(H))
    lon, lat = P2LL.transform(gx.ravel(), gy.ravel())
    return np.asarray(lon), np.asarray(lat)


def sample(arr, px, py, order):
    ok = ~np.isnan(arr)
    v = ndi.map_coordinates(np.where(ok, arr, 0.0), [py, px], order=order, mode="nearest")
    if order == 0: return np.where(ndi.map_coordinates(ok.astype(np.uint8), [py, px], order=0) > 0, v, np.nan)
    w = ndi.map_coordinates(ok.astype(float), [py, px], order=order, mode="nearest")
    return np.where(w > 0.99, v / np.maximum(w, 1e-9), np.nan)


def png_height(f):
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.int64)
    v = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
    h = np.where(v < 2 ** 23, v, v - 2 ** 24).astype(np.float64) * 0.01
    h[(a[..., 0] == 128) & (a[..., 1] == 0) & (a[..., 2] == 0)] = np.nan
    return h


def fetch_dem5(bb):
    """GSI DEM5A (5 m, airborne laser) z15 tiles over the frame → mosaic + its tile origin."""
    os.makedirs("dem5", exist_ok=True)
    def t(lon, lat, z=15):
        n = 2 ** z; r = math.radians(lat)
        return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
    tx0, ty0 = t(bb[0], bb[3]); tx1, ty1 = t(bb[2], bb[1])
    out = np.full(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.nan)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            f = f"dem5/dem5a_15_{tx}_{ty}.png"
            if not os.path.exists(f):
                try:
                    open(f, "wb").write(urllib.request.urlopen(urllib.request.Request(
                        f"https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/15/{tx}/{ty}.png", headers=UA), timeout=60).read())
                except urllib.error.HTTPError as e:
                    if e.code != 404: raise
                    open(f, "wb").close()
            if os.path.getsize(f):
                out[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = png_height(f)
    return out, tx0, ty0


def gsi_points(bb, tiles="../morph/raw/bvmap/z16"):
    """Benchmarks, triangulation points and spot heights from the optimal vector tiles (lon, lat, height, kind, code)."""
    out = []
    for f in sorted(glob.glob(f"{tiles}/16_*.pbf")):
        z, tx, ty = map(int, os.path.basename(f)[:-4].split("_")); n = 2 ** z
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        for lname in ("symbol", "elevation"):
            L = t.get(lname)
            if not L: continue
            for ft in L["features"]:
                p = ft["properties"]; code = p.get("ftCode")
                if code not in (7102, 7103, 7201) or "alti" not in p: continue
                cx, cy = ft["geometry"]["coordinates"]
                x = (tx + cx / L["extent"]) / n; y = (ty + cy / L["extent"]) / n
                lon = x * 360 - 180; lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y))))
                if bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]:
                    out.append((lon, lat, float(p["alti"]), {7102: "triangulation point", 7103: "levelling benchmark",
                                                               7201: "spot height (1:25,000)"}[code], p.get("gcpCode")))
    return sorted(set(out), key=lambda r: r[2])


def gsi_buildings(bb, tiles="../morph/raw/bvmap/z16"):
    import shapely
    from shapely.ops import unary_union
    polys = []
    for f in sorted(glob.glob(f"{tiles}/16_*.pbf")):
        z, tx, ty = map(int, os.path.basename(f)[:-4].split("_")); n = 2 ** z
        lon0, lon1 = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
        lat1, lat0 = (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n)))) for yy in (ty, ty + 1))
        if lon1 < bb[0] or lon0 > bb[2] or lat1 < bb[1] or lat0 > bb[3]: continue
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        L = t.get("building")
        if not L: continue
        ext = L["extent"]
        def tocs(c, tx=tx, ty=ty, ext=ext):
            x = (tx + c[:, 0] / ext) / n; y = (ty + c[:, 1] / ext) / n
            lon = x * 360 - 180; lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y))))
            X, Y = LL2P.transform(lon, lat); return np.column_stack([X, Y])
        for ft in L["features"]:
            if ft["geometry"]["type"] not in ("Polygon", "MultiPolygon"): continue
            g = shapely.clip_by_rect(shapely.make_valid(shape(ft["geometry"])), 0, 0, ext, ext)
            if not g.is_empty: polys.append(shapely.transform(g, tocs))
    return unary_union([p.buffer(0.05) for p in polys]).buffer(-0.05)


def rasterize(polys, x0, y1, W, H):
    """Boolean mask of polygons on the 1 m grid (cell centres; holes respected)."""
    from PIL import ImageDraw
    im = Image.new("1", (W, H), 0); dr = ImageDraw.Draw(im)
    def ring(r): return [(x - x0 - 0.5, y1 - y - 0.5) for x, y in r.coords]
    for g in polys:
        for p in getattr(g, "geoms", [g]):
            if p.geom_type != "Polygon" or p.is_empty: continue
            dr.polygon(ring(p.exterior), fill=1)
            for h in p.interiors: dr.polygon(ring(h), fill=0)
    return np.asarray(im, dtype=bool)


def curvatures(z, sigma):
    """Profile and plan curvature (1/m) of z smoothed with a Gaussian of the given σ (m); rows run south."""
    zs = ndi.gaussian_filter(z, sigma)
    zy_r, zx = np.gradient(zs); zy = -zy_r                      # north-positive y
    zxx = np.gradient(zx, axis=1); zyy = -np.gradient(zy, axis=0); zxy = np.gradient(zx, axis=0) * -1
    p, q, r, s, t = zx, zy, zxx, zxy, zyy
    g2 = p * p + q * q + 1e-12
    prof = -(r * p * p + 2 * s * p * q + t * q * q) / (g2 * (1 + g2) ** 1.5)
    plan = -(t * p * p - 2 * s * p * q + r * q * q) / (g2 ** 1.5)
    return prof.astype(np.float32), plan.astype(np.float32), np.degrees(np.arctan(np.sqrt(g2))).astype(np.float32)


def selftest_curv():
    """A synthetic foot (15° slope meeting a flat plain) must read concave at the junction; a shoulder convex."""
    x = np.arange(200.0)
    prof = np.where(x < 100, (100 - x) * math.tan(math.radians(15)), 0.0)    # slope falls eastward to x = 100
    z = np.tile(prof, (60, 1))
    k, _, _ = curvatures(z, SIG_CURV)
    assert k[30, 100] < -0.01 and abs(k[30, 50]) < 1e-3, (k[30, 100], k[30, 50])
    k2, _, _ = curvatures(-z, SIG_CURV)                         # flipped: a plateau edge (shoulder)
    assert k2[30, 100] > 0.01


def main():
    selftest_curv()
    tz = np.load("terrain.npz"); z = tz["z"].astype(np.float64); x0, y1, W, H = [float(v) for v in tz["frame"]]
    W, H = int(W), int(H)
    st = json.load(open("study.json")); poly = Polygon(st["poly"][0])
    meta = json.load(open("dem1.json"))
    lon, lat = grid_ll(x0, y1, W, H)

    # provenance of every 1 m cell (nearest tile pixel of the DEM1A / DEM5A mosaic)
    px, py = merc_px(lon, lat, meta["z"], meta["tx0"], meta["ty0"])
    src = np.load("dem1_src.npy")
    srcg = ndi.map_coordinates(src, [np.round(py), np.round(px)], order=0).reshape(H, W)
    gx, gy = np.meshgrid(x0 + 0.5 + np.arange(W), y1 - 0.5 - np.arange(H))
    from shapely import contains_xy
    inpoly = contains_xy(poly, gx, gy)
    cov = {"frame_1m_pct": round(100 * float((srcg == 1).sum()) / float((srcg > 0).sum()), 2),
           "frame_5m_cells": int((srcg == 5).sum()), "frame_nodata_cells": int((srcg == 0).sum()),
           "study_1m_pct": round(100 * float((srcg[inpoly] == 1).sum()) / float(inpoly.sum()), 2),
           "study_5m_cells": int((srcg[inpoly] == 5).sum())}

    # DEM5A over the same grid
    bb = [float(v) for v in meta["bbox"]]
    d5, t5x, t5y = fetch_dem5(bb)
    p5x, p5y = merc_px(lon, lat, 15, t5x, t5y)
    z5 = sample(d5, p5x, p5y, 1).reshape(H, W)

    # buildings (bare-ground model is interpolated beneath them)
    from shapely.geometry import box
    frame = box(x0, y1 - H, x0 + W, y1)
    bld = gsi_buildings(bb).intersection(frame)
    under = rasterize(getattr(bld, "geoms", [bld]), x0, y1, W, H)

    zs = ndi.gaussian_filter(np.where(np.isnan(z), np.nanmedian(z), z), 1.0)
    gyr, gxx = np.gradient(zs); slope1 = np.degrees(np.arctan(np.hypot(gxx, gyr)))
    open_flat = (slope1 < 3) & ~under & ~np.isnan(z) & ~np.isnan(z5)
    d = (z5 - z)[open_flat]
    steep = (slope1 >= 20) & ~under & ~np.isnan(z5)
    ds = (z5 - z)[steep]
    cmp5 = {"open_flat_n": int(open_flat.sum()), "open_flat_median_m": round(float(np.median(d)), 3),
            "open_flat_mad_m": round(float(np.median(np.abs(d - np.median(d)))), 3),
            "open_flat_p95_abs_m": round(float(np.percentile(np.abs(d), 95)), 2),
            "steep_rmse_m": round(float(np.sqrt(np.mean(ds ** 2))), 2), "steep_n": int(steep.sum())}

    # channel cross-sections: 1 m vs 5 m depth below the banks, inside the study area
    from shapely.geometry import LineString
    wa = [Polygon(r[0]) for r in st["water_area"]]
    from shapely.ops import unary_union
    chan = unary_union(wa).intersection(poly)
    sections = []
    for yy in np.arange(poly.bounds[1] + 10, poly.bounds[3] - 10, 10.0):
        row = chan.intersection(LineString([(poly.bounds[0], yy), (poly.bounds[2], yy)]))
        if row.is_empty: continue
        cx = (row.bounds[0] + row.bounds[2]) / 2
        r = int(round(y1 - 0.5 - yy)); c = int(round(cx - x0 - 0.5))
        if not (8 <= c < W - 8): continue
        bank1 = np.nanmax(z[r, c - 8:c - 3]); bank2 = np.nanmax(z[r, c + 4:c + 9])
        bank5_1 = np.nanmax(z5[r, c - 8:c - 3]); bank5_2 = np.nanmax(z5[r, c + 4:c + 9])
        # wall-to-wall width on the 1 m model: the unbroken run of cells around the centre lying more than 0.6 m
        # below the lower bank
        lvl = min(bank1, bank2) - 0.6; lo_, hi_ = c, c
        while lo_ - 1 >= 0 and z[r, lo_ - 1] < lvl: lo_ -= 1
        while hi_ + 1 < W and z[r, hi_ + 1] < lvl: hi_ += 1
        sections.append((float(min(bank1, bank2) - np.nanmin(z[r, c - 2:c + 3])),
                         float(min(bank5_1, bank5_2) - np.nanmin(z5[r, c - 2:c + 3])), float(hi_ - lo_ + 1)))
    sec = np.array(sections)
    cmp5.update({"channel_sections": len(sec), "channel_depth_1m_median": round(float(np.median(sec[:, 0])), 2),
                 "channel_depth_5m_median": round(float(np.median(sec[:, 1])), 2),
                 "channel_width_1m_median": round(float(np.median(sec[:, 2])), 1),
                 "channel_width_1m_p25": round(float(np.percentile(sec[:, 2], 25)), 1),
                 "channel_width_1m_p75": round(float(np.percentile(sec[:, 2], 75)), 1)})

    # control points
    pts = gsi_points(bb)
    ctrl = []
    for plon, plat, h, kind, code in pts:
        qx, qy = merc_px(np.array([plon]), np.array([plat]), meta["z"], meta["tx0"], meta["ty0"])
        dem = np.load("dem1.npy")
        v = float(sample(dem, qx, qy, 1)[0])
        # the highest ground within 3 m (a benchmark or pillar sits on its local top; positions carry ~1–2 m error)
        i, j = int(round(qy[0])), int(round(qx[0]))
        win = dem[max(i - 3, 0):i + 4, max(j - 3, 0):j + 4]
        cx, cy = LL2P.transform(plon, plat)
        ctrl.append({"kind": kind, "code": code, "lon": round(plon, 6), "lat": round(plat, 6), "h": h,
                     "dem1a": round(v, 2), "diff": round(v - h, 2), "dem1a_max3m": round(float(np.nanmax(win)), 2),
                     "dist_m": round(poly.distance(Point(cx, cy)))})            # from the study area

    # derivatives
    zf = np.where(np.isnan(z), np.nanmedian(z), z)
    lrm = (zf - ndi.gaussian_filter(zf, SIG_LRM)).astype(np.float32)
    prof, plan, slope_c = curvatures(zf, SIG_CURV)
    lrm[np.isnan(z)] = np.nan; prof[np.isnan(z)] = np.nan; plan[np.isnan(z)] = np.nan
    np.savez_compressed("terrain_plus.npz", lrm=lrm, prof=prof, plan=plan, src=srcg.astype(np.uint8),
                        under=under, z5=z5.astype(np.float32), frame=tz["frame"])
    # the share under the outlines is counted by cell centre (= footprint area); the mask `under`, which the analyses use
    # to leave interpolated ground out, also takes every cell an outline crosses (a deliberate margin of about half a cell)
    exact = contains_xy(bld, gx, gy)
    bshare = {"study_under_buildings_pct": round(100 * float(exact[inpoly].mean()), 1),
              "frame_under_buildings_pct": round(100 * float(exact.mean()), 1),
              "study_mask_pct": round(100 * float(under[inpoly].mean()), 1)}
    audit = {"coverage": cov, "dem5_vs_1": cmp5, "control": ctrl, "buildings": bshare,
             "sigma_lrm_m": SIG_LRM, "sigma_curv_m": SIG_CURV,
             "lrm_p": {k: round(float(np.nanpercentile(lrm[inpoly], q)), 2) for k, q in (("p01", 1), ("p50", 50), ("p99", 99))}}
    json.dump(audit, open("terrain_audit.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(audit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
