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
  3. fit     reported as the distance of road-parcel outlines to GSI road edges (median, 75th percentile, share
             within 1.5 m) and the school outline's distance to OSM's.

The drawings must be enlarged 13–16 % (31 % in area) and turned about 14° to fit the ground, the usual state of
Meiji-derived cadastral drawings (縄伸び: land measured short when it was first registered). Positions remain approximate (the
page says so); directions are what the alignment test uses. Writes parcels.json (transform, fit, every parcel in
JGD2011 / CS VI metres with its 地番, 大字, 丁目 and class: private / road / water / strip).
"""
import collections, io, json, math, os, pickle, re, sys, zipfile
import numpy as np
from scipy import ndimage as ndi, optimize
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, LineString, box
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
    a, b, c, d = ra.x[:4]
    rot_aff = math.degrees(math.atan2(c - b, a + d))
    out = {"sheet": SHEET, "name": meta.get("地図名"), "crs": meta.get("座標系"), "n_parcels": len(idx),
           "anchor": {"parcel": "".join(ANCHOR), "rotation_deg": round(th, 1), "scale": round(math.exp(ls), 3)},
           "sim": {"params": [float(v) for v in rs.x], "rotation_deg": round(th2, 1), "scale": round(s2, 3), **fit(rs.x, "sim")},
           "aff": {"params": [float(v) for v in ra.x], "rotation_deg": round(rot_aff, 1),
                   "scale_x": round(math.hypot(a, c), 3), "scale_y": round(math.hypot(b, d), 3), **fit(ra.x, "aff")},
           "c0": c0.tolist(), "use": "aff", "parcels": []}
    for i in idx:
        r = fude[i][0]
        for kind in ("aff", "sim"):
            g = stf(geoms[i], lambda C, k=kind: apply(out[k]["params"], C, c0, k))
            rings = [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords] for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon"]
            if kind == "aff": rec = {"chiban": r["地番"], "oaza": r["大字名"], "chome": r["丁目名"], "kind": kind_of(r["地番"]), "rings": rings}
            else: rec["rings_sim"] = rings
        out["parcels"].append(rec)
    json.dump(out, open("parcels.json", "w"), ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k not in ("parcels",)}, ensure_ascii=False, indent=1))
    print("parcels by kind", dict(collections.Counter(p["kind"] for p in out["parcels"])))


if __name__ == "__main__":
    main()
