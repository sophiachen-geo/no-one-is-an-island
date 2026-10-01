"""Kamikura micro-study, step 7: put the Ministry of Justice parcel map on the ground.

The MoJ map for 千穂 / 神倉 (登記所備付地図データ 2026, 30207-1704-59, 「新宮・千穂一丁目・神倉一丁目他」) is in
arbitrary plane coordinates (任意座標系) and was digitised from the cadastral drawings (座標値種別 図上測量): blocks of
drawings placed side by side, each with its own offset, rotation and scale. Its roads (地番 道-…) and waterways
(水-…) are parcels of their own, which is what makes registration possible. The fragment that holds 千穂一丁目 (the
study area) is registered as one piece:

  1. anchor  the largest parcel, 千穂一丁目 715-3, is the school compound; its outline is matched to the school's
             OSM outline (way 1333972521) as a similarity transform (rotation, scale, shift; 36 starting angles);
  2. roads   from there, the outline of the fragment's road parcels (道) is fitted to GSI's 1:2,500 road edges
             (optimal vector tiles, ftCodes 2201/2203/2204/2221) by minimising the mean distance to the nearest
             edge, truncated at 6 m (chamfer matching) — first as a similarity, then as an affine transform.
  3. warp    a thin-plate spline on top of the affine fit tests for stretch that varies across the sheet (縄伸び
             need not be uniform): control pairs every 5 m along the road-parcel outlines, each to the nearest GSI
             road edge within 6 m; its smoothing is chosen by leaving out one zone (north, middle, south third of the
             fragment) at a time and scoring the left-out zone. Here the stiffest setting wins (the spline adds
             nothing the road edges can confirm), so the page keeps the affine fit and the spline is a sensitivity run.
  4. fit     reported as the distance of road-parcel outlines to GSI road edges (median, 75th percentile, share
             within 1.5 m), overall and by zone for each of the three registrations (the spline's by zone as
             left-out scores), and the school outline's distance to OSM's.

The drawings must be enlarged 13–16 % (31 % in area) and turned about 14° to fit the ground, the usual state of
Meiji-derived cadastral drawings (縄伸び: land measured short when it was first registered). Positions remain approximate (the
page says so); directions are what the alignment test uses. Writes parcels.json (transform, fit, every parcel in
JGD2011 / CS VI metres with its 地番, 大字, 丁目 and class: private / road / water / strip; rings = affine, the
registration used; rings_sim and rings_tps for the sensitivity runs of step 8).
"""
import collections, io, json, math, os, pickle, re, sys, zipfile
import numpy as np
from scipy import ndimage as ndi, optimize
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union
from shapely import STRtree, transform as stf
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsi import tiles_layers                                   # noqa: E402

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
SHEET = "30207-1704-59"
ANCHOR = ("千穂", "１丁目", "715-3")
SCHOOL_WAY = 1333972521
TRUNC = 6.0


def edges_grid(lines, x0, y1, W, H):
    from PIL import Image, ImageDraw
    im = Image.new("1", (W, H), 0); dr = ImageDraw.Draw(im)
    for g in lines:
        for l in getattr(g, "geoms", [g]):
            if l.geom_type == "Polygon": l = l.exterior
            if l.geom_type != "LineString": continue
            pts = [(x - x0 - 0.5, y1 - y - 0.5) for x, y in l.coords]
            if len(pts) > 1: dr.line(pts, fill=1, width=1)
    return ndi.distance_transform_edt(~np.asarray(im, dtype=bool))


def outline_points(F, step=1.0):
    pts = []
    for p in getattr(F, "geoms", [F]):
        if p.geom_type != "Polygon": continue
        for ring in [p.exterior] + list(p.interiors):
            L = LineString(ring.coords); n = max(int(L.length / step), 2)
            pts += [L.interpolate(i * step).coords[0] for i in range(n)]
    return np.array(pts)


def chamfer(P, dt, x0, y1):
    c = P[:, 0] - x0 - 0.5; r = y1 - 0.5 - P[:, 1]
    return np.minimum(ndi.map_coordinates(dt, [r, c], order=1, mode="constant", cval=TRUNC), TRUNC)


def apply(params, P, c0, kind):
    """sim: (θ°, ln s, tx, ty) about c0; aff: (a, b, c, d, tx, ty) about c0 — both map c0 to (tx, ty)."""
    Q = np.asarray(P) - c0
    if kind == "sim":
        th, ls, tx, ty = params; s = math.exp(ls); ct, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
        return np.column_stack([s * (ct * Q[:, 0] - sn * Q[:, 1]) + tx, s * (sn * Q[:, 0] + ct * Q[:, 1]) + ty])
    a, b, c, d, tx, ty = params
    return np.column_stack([a * Q[:, 0] + b * Q[:, 1] + tx, c * Q[:, 0] + d * Q[:, 1] + ty])


def load_sheet(zpath):
    from mojparse import parse
    z = zipfile.ZipFile(zpath)
    inner = zipfile.ZipFile(io.BytesIO(z.read(f"{SHEET}.zip")))
    meta, fude, _ = parse(inner.read(f"{SHEET}.xml"))
    return meta, fude


def kind_of(chiban):
    # "private" here means a numbered lot (地番): the drawing records lots, not owners (the school's parcel is one);
    # the page and the downloads call them "numbered"
    if chiban.startswith("道"): return "road"
    if chiban.startswith("水"): return "water"
    if chiban.startswith("長狭物"): return "strip"
    return "private" if re.match(r"\d", chiban) else "other"


def main():
    meta, fude = load_sheet("moj/30207-1704-2026.zip")
    geoms = [g.buffer(0) for _, g in fude]
    U = unary_union([g.buffer(0.6) for g in geoms]).buffer(-0.6)
    frags = list(getattr(U, "geoms", [U]))
    tree = STRtree(geoms)
    def members(F): return [i for i in tree.query(F, predicate="intersects") if F.buffer(-0.3).intersects(geoms[i])]
    count = lambda F: sum(1 for i in members(F) if fude[i][0]["大字名"] == "千穂" and fude[i][0]["丁目名"] == "１丁目")
    F = max(frags, key=count)
    idx = members(F)

    tz = np.load("terrain.npz"); x0, y1, W, H = [float(v) for v in tz["frame"]]; W, H = int(W), int(H)
    frame = box(x0, y1 - H, x0 + W, y1)
    L = tiles_layers()
    roads = [l.intersection(frame) for c, l in L["road_edge"] if c in (2201, 2203, 2204, 2221)]
    dt = edges_grid([l for l in roads if not l.is_empty], x0, y1, W, H)

    osm = json.load(open("osm.json"))["elements"]
    school = [Polygon([LL2P.transform(p["lon"], p["lat"]) for p in e["geometry"]]) for e in osm
              if e["type"] == "way" and e["id"] == SCHOOL_WAY][0]
    anchor = [geoms[i] for i in idx if (fude[i][0]["大字名"], fude[i][0]["丁目名"], fude[i][0]["地番"]) == ANCHOR][0]

    # 1. anchor: the school parcel onto the school outline
    A = outline_points(anchor); B = outline_points(school); tB = cKDTree(B)
    ca, cb = A.mean(0), B.mean(0)
    def cost(p):
        Q = apply(p, A, ca, "sim")
        return np.mean(np.minimum(tB.query(Q)[0], 15) ** 2) + np.mean(np.minimum(cKDTree(Q).query(B)[0], 15) ** 2)
    best = min((optimize.minimize(cost, [th, math.log(1.1), cb[0], cb[1]], method="Nelder-Mead",
                                  options={"maxiter": 4000, "xatol": 0.01, "fatol": 1e-5}) for th in range(-180, 180, 10)),
               key=lambda r: r.fun)
    c0 = outline_points(F).mean(0)
    th, ls = best.x[0], best.x[1]
    img_c0 = apply(best.x, c0[None, :], ca, "sim")[0]
    init = [th, ls, img_c0[0], img_c0[1]]

    # 2. roads: the fragment's road parcels onto GSI road edges
    road_pts = outline_points(unary_union([geoms[i] for i in idx if kind_of(fude[i][0]["地番"]) == "road"]))
    fs = lambda p: chamfer(apply(p, road_pts, c0, "sim"), dt, x0, y1).mean()
    rs = optimize.minimize(fs, init, method="Nelder-Mead", options={"xatol": 0.005, "fatol": 1e-6, "maxiter": 8000})
    th2, ls2, tx2, ty2 = rs.x; s2 = math.exp(ls2); ct, sn = math.cos(math.radians(th2)), math.sin(math.radians(th2))
    fa = lambda p: chamfer(apply(p, road_pts, c0, "aff"), dt, x0, y1).mean()
    ra = optimize.minimize(fa, [s2 * ct, -s2 * sn, s2 * sn, s2 * ct, tx2, ty2], method="Nelder-Mead",
                           options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 20000})

    def fit(Tp, kind):
        d = chamfer(apply(Tp, road_pts, c0, kind), dt, x0, y1)
        ds = tB.query(apply(Tp, A, c0, kind))[0]
        return {"road_median_m": round(float(np.median(d)), 2), "road_p75_m": round(float(np.percentile(d, 75)), 2),
                "road_within1_5_pct": round(100 * float((d <= 1.5).mean()), 1),
                "school_median_m": round(float(np.median(ds)), 2)}
    # 3. thin-plate spline on the affine positions; smoothing and the comparison by leave-one-zone-out: each zone
    #    (south, middle, north third of the fragment) is left out in turn, the affine (or similarity) is refitted on
    #    the other two, the spline is trained on their control pairs, and all three are scored on the left-out zone
    from scipy.interpolate import RBFInterpolator
    edge_pts = np.vstack([np.array([l.interpolate(t).coords[0] for t in np.arange(0, l.length, 0.5)])
                          for g in roads for l in getattr(g, "geoms", [g]) if l.geom_type == "LineString" and l.length > 1])
    tE = cKDTree(edge_pts)
    Qa = apply(ra.x, road_pts, c0, "aff")
    keep = np.zeros(len(Qa), bool); keep[::5] = True                 # outline points are 1 m apart: one pair every 5 m
    ymin, ymax = Qa[:, 1].min(), Qa[:, 1].max(); cuts = [ymin + (ymax - ymin) * k / 3 for k in (1, 2)]
    zq = np.digitize(Qa[:, 1], cuts)                                 # 0 south, 1 middle, 2 north (by the full affine fit)
    def pairs(Q, sel):
        d, i = tE.query(Q[sel]); ok = d <= TRUNC; return Q[sel][ok], edge_pts[i[ok]]
    def spline(Q, sel, sm):
        src, dst = pairs(Q, sel); return RBFInterpolator(src, dst - src, kernel="thin_plate_spline", smoothing=sm, degree=1)
    out_fit = {}
    for zz in range(3):                                              # the rigid fits without each zone
        m = zq == zz
        for k, x_init in (("sim", rs.x), ("aff", ra.x)):
            f_out = lambda p, k=k, m=m: chamfer(apply(p, road_pts[~m], c0, k), dt, x0, y1).mean()
            out_fit[(k, zz)] = optimize.minimize(f_out, x_init, method="Nelder-Mead", options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 20000}).x
    def left_out(zz, sm):
        m = zq == zz; Q = apply(out_fit[("aff", zz)], road_pts, c0, "aff")
        RBo = spline(Q, keep & ~m, sm); return chamfer(Q[m] + RBo(Q[m]), dt, x0, y1)
    grid_sm = [1.0, 10.0, 100.0, 1e3, 1e4, 1e5, 1e6]
    scores = {sm: float(np.median(np.concatenate([left_out(zz, sm) for zz in range(3)]))) for sm in grid_sm}
    sm_best = min(scores, key=scores.get)
    RB = spline(Qa, keep, sm_best)                                   # the fitted warp on all pairs, built once
    def tps_geom(g):
        """warp ring by ring and close each ring exactly (the spline maps a ring's equal first and last points to values
        that can differ in the last bits)"""
        polys = []
        for q in getattr(g, "geoms", [g]):
            if q.geom_type != "Polygon": continue
            def ring(cs):
                P = apply(ra.x, np.asarray(cs)[:, :2], c0, "aff"); P = P + RB(P); P[-1] = P[0]; return P
            polys.append(Polygon(ring(q.exterior.coords), [ring(h.coords) for h in q.interiors]))
        return polys[0] if len(polys) == 1 else MultiPolygon(polys)
    Qt = Qa + RB(Qa); Qs = apply(rs.x, road_pts, c0, "sim")
    tps_zones = []
    for zz, nm in ((2, "north"), (1, "middle"), (0, "south")):
        m = zq == zz; row = {"zone": nm, "n_points": int(m.sum())}
        for k, P in (("sim", Qs), ("aff", Qa), ("tps", Qt)):
            dz = chamfer(P[m], dt, x0, y1); row[k + "_median_m"] = round(float(np.median(dz)), 3); row[k + "_within1_5_pct"] = round(100 * float((dz <= 1.5).mean()), 1)
        for k in ("sim", "aff"):
            do = chamfer(apply(out_fit[(k, zz)], road_pts[m], c0, k), dt, x0, y1)
            row[k + "_left_out_median_m"] = round(float(np.median(do)), 3); row[k + "_left_out_within1_5_pct"] = round(100 * float((do <= 1.5).mean()), 1)
        cv = left_out(zz, sm_best)
        row["tps_left_out_median_m"] = round(float(np.median(cv)), 3); row["tps_left_out_within1_5_pct"] = round(100 * float((cv <= 1.5).mean()), 1)
        tps_zones.append(row)
    dT = chamfer(Qt, dt, x0, y1); n_pairs = len(pairs(Qa, keep)[0])

    a, b, c, d = ra.x[:4]
    rot_aff = math.degrees(math.atan2(c - b, a + d))
    out = {"sheet": SHEET, "name": meta.get("地図名"), "crs": meta.get("座標系"), "n_parcels": len(idx),
           "anchor": {"parcel": "".join(ANCHOR), "rotation_deg": round(th, 1), "scale": round(math.exp(ls), 3)},
           "sim": {"params": [float(v) for v in rs.x], "rotation_deg": round(th2, 1), "scale": round(s2, 3), **fit(rs.x, "sim")},
           "aff": {"params": [float(v) for v in ra.x], "rotation_deg": round(rot_aff, 1),
                   "scale_x": round(math.hypot(a, c), 3), "scale_y": round(math.hypot(b, d), 3), **fit(ra.x, "aff")},
           "tps": {"smoothing": sm_best, "cv_median_m_by_smoothing": {str(k): round(v, 3) for k, v in scores.items()}, "n_pairs": int(n_pairs),
                   "road_median_m": round(float(np.median(dT)), 2), "road_within1_5_pct": round(100 * float((dT <= 1.5).mean()), 1), "zones": tps_zones},
           "c0": c0.tolist(), "use": "aff", "parcels": []}
    for i in idx:
        r = fude[i][0]
        for kind in ("aff", "sim", "tps"):
            if kind == "tps": g = tps_geom(geoms[i])
            else: g = stf(geoms[i], lambda C, k=kind: apply(out[k]["params"], C, c0, k))
            rings = [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords] for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon"]
            if kind == "aff": rec = {"chiban": r["地番"], "oaza": r["大字名"], "chome": r["丁目名"], "kind": kind_of(r["地番"]), "rings": rings}
            else: rec["rings_" + kind] = rings
        out["parcels"].append(rec)
    json.dump(out, open("parcels.json", "w"), ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k not in ("parcels",)}, ensure_ascii=False, indent=1))
    print("parcels by kind", dict(collections.Counter(p["kind"] for p in out["parcels"])))


if __name__ == "__main__":
    main()
