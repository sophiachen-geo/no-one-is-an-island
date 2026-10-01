"""Kamikura micro-study, step 3: the study polygon, the transect, statistics and the alignment test.

Reads (work dir): osm.json, terrain.npz/.json (02), ../morph/buildings.geojson (GSI footprints), ../ksj/* hazard
and planning layers. Writes study.json (all geometry in JGD2011 / CS VI metres) for 04_export.py.

The polygon follows four rules (see the README in this folder):
  W  the line 25 m upslope of the 1 m slope break (02_terrain.py)
  E  the street that bounds the 千穂 elementary-school compound on the east, continued south by the lane that
     carries the same line (OSM 121367848 · 1031510641 · 121367953)
  N  the lane that closes the first full block north of the school and the temple row at the mountain foot
     (OSM 266991552 · 121369902), carried straight west to the W line
  S  the street just south of the shrine-entrance cluster (OSM 121367975 · 121370515 · 499568826), carried straight
     west across the foot of the steps to the W line
"""
import json, math
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, Polygon, MultiPolygon, LineString, MultiLineString, Point, box, mapping
from shapely.ops import unary_union, polygonize, linemerge, substring

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
P2LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)
KSJ = "../ksj"

N_WAYS = [266991552, 121369902]
E_WAYS = [121367848, 1031510641, 121367953]
S_PIECES = [(121367975, (135.98552, 33.72383), (135.98507, 33.72390)),    # (way, from, to): only the stretch that
            (121370515, (135.98507, 33.72390), (135.98463, 33.72393)),    # carries the edge line
            (499568826, (135.98463, 33.72393), (135.98423, 33.72396))]
SCHOOL = 1333972521
PRECINCTS = [500803106]                      # 神倉神社's lower precinct (west of the stream)
IZUMO = 500803107                            # the grounds east of it hold the 出雲大社新宮教会 (its hall, torii and board), not the shrine
STREAMS = {83739066: "市田川", 499568828: "Kamikura-yama stream", 83745066: "市田川", 83741819: "浮島川", 83745022: "浮島川"}
STEPS = 121366071
SUMMIT = 2270139651                          # 神倉神社 (summit shrine, at Gotobiki-iwa)
CITY_HALL = 1423067948                       # 新宮市役所
ENTRANCE = (135.98419, 33.72433)             # west end of the bridge over 市田川 at the foot of the steps (OSM 121366834)


def P(lon, lat):
    x, y = LL2P.transform(lon, lat); return (x, y)


def ll(x, y):
    lon, lat = P2LL.transform(x, y); return (round(lon, 7), round(lat, 7))


def way_line(e):
    return LineString([P(p["lon"], p["lat"]) for p in e["geometry"]])


def chain(ways, osm, max_gap=15.0):
    """Join OSM ways, in the order given, into one line; consecutive ways may meet at a shared node or across a
    short gap (two ways ending on the same cross street), bridged straight."""
    out = []
    for w in ways:
        c = list(way_line(osm[w]).coords)
        if out:
            end = out[-1]
            if math.dist(end, c[-1]) < math.dist(end, c[0]): c = c[::-1]
            if math.dist(end, c[0]) > max_gap: raise SystemExit(f"way {w} is {math.dist(end, c[0]):.0f} m from the chain")
            if math.dist(end, c[0]) < 0.01: c = c[1:]
        elif len(ways) > 1:
            nxt = list(way_line(osm[ways[1]]).coords)
            if min(math.dist(c[0], nxt[0]), math.dist(c[0], nxt[-1])) < min(math.dist(c[-1], nxt[0]), math.dist(c[-1], nxt[-1])): c = c[::-1]
        out += c
    return LineString(out)


def piece(osm, w, a, b):
    """The part of an OSM way between the points nearest to a and b (lon, lat), oriented a → b."""
    g = way_line(osm[w]); da, db = g.project(Point(*P(*a))), g.project(Point(*P(*b)))
    s = substring(g, min(da, db), max(da, db))
    return s if da <= db else LineString(list(s.coords)[::-1])


def extend_west(line, dx=80.0):
    """Carry the west end of a roughly east-west line straight west (constant northing) by dx metres."""
    c = list(line.coords)
    if c[0][0] > c[-1][0]: c = c[::-1]
    return LineString([(c[0][0] - dx, c[0][1])] + c)


def gsi_water(bbox_ll, tiles="../morph/raw/bvmap/z16"):
    """GSI optimal vector tiles (experimental_bvmap, z16): water areas (ftCode 5000, the drawn extent of a river
    between its banks) and single-line streams (5301), in CS VI metres. Pieces cut at tile edges are re-joined."""
    import glob, os, mapbox_vector_tile, shapely
    polys, lines = [], []
    for f in sorted(glob.glob(f"{tiles}/16_*.pbf")):
        z, tx, ty = map(int, os.path.basename(f)[:-4].split("_")); n = 2 ** z
        lon0, lon1 = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
        lat1, lat0 = (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n)))) for yy in (ty, ty + 1))
        if lon1 < bbox_ll[0] or lon0 > bbox_ll[2] or lat1 < bbox_ll[1] or lat0 > bbox_ll[3]: continue
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        for lname in ("waterarea", "river"):
            L = t.get(lname)
            if not L: continue
            ext = L["extent"]
            def tocs(c, tx=tx, ty=ty, ext=ext):
                x = (tx + c[:, 0] / ext) / n; y = (ty + c[:, 1] / ext) / n
                lon = x * 360 - 180; lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y))))
                X, Y = LL2P.transform(lon, lat); return np.column_stack([X, Y])
            for ft in L["features"]:
                code = ft["properties"].get("ftCode"); g = shape(ft["geometry"])
                if lname == "waterarea" and code == 5000:
                    g = shapely.clip_by_rect(shapely.make_valid(g), 0, 0, ext, ext)
                    if not g.is_empty: polys.append(shapely.transform(g, tocs))
                elif lname == "river" and code == 5301:
                    lines.append(shapely.transform(g, tocs))
    area = unary_union([p.buffer(0.05) for p in polys]).buffer(-0.05)
    return area, unary_union(lines)


def centreline(poly, y_top, y_bottom, step=1.0, start_x=None):
    """Centre line of an elongated north–south water area: the midpoint of each east–west chord, following the chord
    nearest the previous point (exact for straight reaches, close on bends)."""
    pts, x_prev = [], start_x
    for y in np.arange(y_top, y_bottom, -step):
        row = poly.intersection(LineString([(poly.bounds[0] - 1, y), (poly.bounds[2] + 1, y)]))
        segs = [g for g in getattr(row, "geoms", [row]) if g.geom_type == "LineString" and g.length > 0]
        if not segs: continue
        mids = [((g.bounds[0] + g.bounds[2]) / 2, g.length) for g in segs]
        x = min(mids, key=lambda m: abs(m[0] - x_prev))[0] if x_prev is not None else max(mids, key=lambda m: m[1])[0]
        pts.append((x, y)); x_prev = x
    return LineString(pts).simplify(0.3)


def axial_stats(angles_deg, weights, period):
    """Mean direction and concentration of axial data with the given period (180 = lines, 90 = rectangles)."""
    k = 360.0 / period
    a = np.radians(np.asarray(angles_deg) * k); w = np.asarray(weights, float)
    C, S = (w * np.cos(a)).sum() / w.sum(), (w * np.sin(a)).sum() / w.sum()
    return (math.degrees(math.atan2(S, C)) / k) % period, float(math.hypot(C, S))


def seg_bearings(line, step=None):
    """Bearing (degrees clockwise from grid north, mod 180) and length of each segment of a line."""
    c = np.asarray(line.coords)
    d = np.diff(c, axis=0); L = np.hypot(d[:, 0], d[:, 1])
    b = (np.degrees(np.arctan2(d[:, 0], d[:, 1])) + 360) % 180
    return b[L > 0], L[L > 0]


def adiff(a, b, period):
    d = abs((a - b) % period); return min(d, period - d)


def main():
    osm_l = json.load(open("osm.json"))["elements"]
    osm = {e["id"]: e for e in osm_l if e["type"] == "way" and e.get("geometry")}
    nodes = {e["id"]: e for e in osm_l if e["type"] == "node"}
    tj = json.load(open("terrain.json")); tz = np.load("terrain.npz")
    z, slope, mountain = tz["z"], tz["slope"], tz["mountain"]
    x0, y1, W, H = tz["frame"]

    def rc(x, y):
        return int(y1 - y), int(x - x0)

    # ------------------------------------------------------------------ the four edges
    north = extend_west(chain(N_WAYS, osm))
    sc = []
    for w, a, b in S_PIECES:
        c = list(piece(osm, w, a, b).coords); sc += c if not sc else c[1:]
    south = extend_west(LineString(sc), 120)
    east = chain(E_WAYS, osm)
    lo_y, hi_y = min(south.bounds[1], south.bounds[3]) - 60, max(north.bounds[1], north.bounds[3]) + 60
    offs = [LineString(l) for l in tj["offset"]]
    west = [l.intersection(box(east.bounds[0] - 400, lo_y, east.bounds[2], hi_y)) for l in offs]
    west = unary_union([g for g in west if not g.is_empty])
    faces = list(polygonize(unary_union([north, south, east, west])))
    inside = Point(*P(135.98500, 33.72500))                      # the school ground
    poly = [f for f in faces if f.contains(inside)]
    if len(poly) != 1: raise SystemExit(f"polygon not closed: {len(faces)} faces")
    poly = poly[0]
    area = poly.area
    minx, miny, maxx, maxy = poly.bounds

    # ------------------------------------------------------------------ terrain inside
    xs = x0 + 0.5 + np.arange(int(W)); ys = y1 - 0.5 - np.arange(int(H))
    from shapely import contains_xy
    gx, gy = np.meshgrid(xs, ys)
    inP = contains_xy(poly, gx, gy)
    zin = z[inP & ~np.isnan(z)]
    m_in = mountain[inP]
    # break line inside the polygon (for the alignment test and the map)
    brk = unary_union([LineString(l) for l in tj["break"]])
    brk_in = brk.intersection(poly)
    brk_band = brk.intersection(box(minx - 200, miny - 150, maxx, maxy + 150))

    # ------------------------------------------------------------------ features
    school = Polygon([P(p["lon"], p["lat"]) for p in osm[SCHOOL]["geometry"]])
    prec = [Polygon([P(p["lon"], p["lat"]) for p in osm[w]["geometry"]]) for w in PRECINCTS]
    izumo = Polygon([P(p["lon"], p["lat"]) for p in osm[IZUMO]["geometry"]])
    streams = {w: way_line(osm[w]) for w in STREAMS if w in osm}
    # the channel itself from GSI (OSM maps only its southern half): water area → centre line from the north end
    WATER, SINGLE = gsi_water((135.9795, 33.7195, 135.9935, 33.7285))
    osm_ichida = streams[83739066]
    comp = [g for g in getattr(WATER, "geoms", [WATER]) if g.intersects(osm_ichida.buffer(3))]
    CH = unary_union(comp)
    ch_top = CH.bounds[3] - 4.0                                   # stop short of the eastward turn at the north end
    ichida = centreline(CH, ch_top, max(CH.bounds[1], poly.bounds[1] - 400), start_x=None)
    ichida_in = ichida.intersection(poly)
    mstream = min((l for l in getattr(SINGLE, "geoms", [SINGLE]) if l.distance(Point(*P(135.98424, 33.72437))) < 15),
                  key=lambda l: -l.length, default=streams[499568828])
    mstream_in = mstream.intersection(poly)
    ch_width = CH.intersection(poly).area / max(1.0, ichida_in.length)          # mean width = area ÷ length
    mstream_src = "GSI 5301" if mstream is not streams[499568828] else "OSM 499568828"
    roads, paths = [], []
    for e in osm.values():
        t = e.get("tags", {})
        if "highway" not in t: continue
        g = way_line(e)
        if not g.intersects(poly): continue
        (paths if t["highway"] in ("path", "footway", "steps", "track", "pedestrian") else roads).append((e["id"], t["highway"], g))
    road_len = sum(g.intersection(poly).length for _, _, g in roads)
    path_len = sum(g.intersection(poly).length for _, _, g in paths)

    # buildings (GSI) with centroid inside
    B = json.load(open("../morph/buildings.geojson"))["features"]
    fx0, fy0, fx1, fy1 = x0, y1 - H, x0 + W, y1
    blds = []
    for f in B:
        c = f["geometry"]["coordinates"][0]
        if not (135.979 < c[0][0] < 135.994 and 33.719 < c[0][1] < 33.729): continue
        pg = Polygon([P(*q) for q in c]).buffer(0)
        if pg.is_empty or pg.area < 4: continue
        blds.append({"g": pg, "code": f["properties"]["ftCode"]})
    for b in blds:
        b["in"] = poly.contains(b["g"].centroid)
        r = b["g"].minimum_rotated_rectangle; cc = np.asarray(r.exterior.coords)[:4]
        e1, e2 = cc[1] - cc[0], cc[2] - cc[1]
        l1, l2 = np.hypot(*e1), np.hypot(*e2)
        long = e1 if l1 >= l2 else e2
        b["axis"] = (math.degrees(math.atan2(long[0], long[1])) + 360) % 180
        b["grid"] = b["axis"] % 90
        b["elong"] = max(l1, l2) / max(1e-6, min(l1, l2))
    bin_ = [b for b in blds if b["in"]]
    foot = sum(b["g"].intersection(poly).area for b in bin_)
    robust = sum(1 for b in bin_ if b["code"] in (3102, 3103, 3112))

    # ------------------------------------------------------------------ hazards and planning, share of the polygon
    def feats(fn, filt=lambda p: True):
        out = []
        for ft in json.load(open(fn, encoding="utf-8"))["features"]:
            if not ft.get("geometry") or not filt(ft["properties"]): continue
            g = shape(ft["geometry"])
            if not g.intersects(box(135.97, 33.71, 136.0, 33.735)): continue
            out.append(g)
        return out

    def proj(g):
        from shapely.ops import transform
        return transform(lambda x, y, z=None: LL2P.transform(x, y), g)

    frame_p = box(fx0, fy0, fx1, fy1)
    TS = proj(unary_union([g.buffer(0) for g in feats(f"{KSJ}/A40-16_30_GML/A40-16_30.geojson")])).intersection(frame_p)
    FL = proj(unary_union([g.buffer(0) for fn in ("8606010001", "8606010002", "8606010006")
                           for g in feats(f"{KSJ}/20_想定最大規模/A31a-20-25_86_{fn}_10.geojson")])).intersection(frame_p)
    a33 = json.load(open(f"{KSJ}/A33-25_30Polygon.geojson", encoding="utf-8"))["features"]
    red = [shape(f["geometry"]).buffer(0) for f in a33 if f["properties"]["A33_002"] in (2, 4) and shape(f["geometry"]).intersects(box(135.97, 33.71, 136.0, 33.735))]
    yel = [shape(f["geometry"]).buffer(0) for f in a33 if f["properties"]["A33_002"] not in (2, 4) and shape(f["geometry"]).intersects(box(135.97, 33.71, 136.0, 33.735))]
    by_kind = {}
    for f in a33:
        g = shape(f["geometry"])
        if not g.intersects(box(135.97, 33.71, 136.0, 33.735)): continue
        by_kind.setdefault(f["properties"]["A33_001"], []).append(g.buffer(0))
    SLOPE = proj(unary_union(by_kind.get(1, []))).intersection(frame_p)     # 急傾斜地の崩壊 (slope failure)
    DEBRIS = proj(unary_union(by_kind.get(2, []))).intersection(frame_p)    # 土石流 (debris flow)
    RED = proj(unary_union(red)).intersection(frame_p) if red else Polygon()
    YEL = proj(unary_union(yel)).intersection(frame_p).difference(RED) if yel else Polygon()
    rit = json.load(open(f"{KSJ}/A55-24_30207_GEOJSON/30207_ritteki.geojson", encoding="utf-8"))["features"]
    RIZ = proj(unary_union([shape(f["geometry"]).buffer(0) for f in rit if f["properties"]["AreaType"] == "居住誘導区域"])).intersection(frame_p)
    UF = proj(unary_union([shape(f["geometry"]).buffer(0) for f in rit if f["properties"]["AreaType"] == "都市機能誘導区域"])).intersection(frame_p)

    def share(g): return round(100 * poly.intersection(g).area / area, 1)

    # ------------------------------------------------------------------ transect: summit → entrance → city hall
    # down the mountain on the pilgrims' own route: summit shrine → path to the top of the stairway (OSM 121369321) →
    # the stone steps (OSM 121366071) → the bridge over 市田川; then straight east across the town to the city hall
    p0 = P(nodes[SUMMIT]["lon"], nodes[SUMMIT]["lat"]); p1 = P(*ENTRANCE); p2 = P(nodes[CITY_HALL]["lon"], nodes[CITY_HALL]["lat"])
    climb = list(chain([121369321, 121366071], osm).coords)
    if math.dist(climb[0], p0) > math.dist(climb[-1], p0): climb = climb[::-1]
    leg1 = [p0] + [q for q in climb if math.dist(q, p0) > 0.5] + [p1]
    tr = LineString(leg1 + [p2])
    from scipy.ndimage import map_coordinates
    dd = np.arange(0, tr.length, 1.0)
    pts = [tr.interpolate(d) for d in dd]
    px = np.array([p.x for p in pts]); py = np.array([p.y for p in pts])
    zz = map_coordinates(np.where(np.isnan(z), np.nanmedian(z), z), [y1 - py - 0.5, px - x0 - 0.5], order=1)
    mm = map_coordinates(mountain.astype(float), [y1 - py - 0.5, px - x0 - 0.5], order=0) > 0.5
    bld_u = unary_union([b["g"] for b in blds])
    water_u = unary_union([WATER.buffer(0.5), SINGLE.buffer(1.5)] + [streams[w].buffer(2.5) for w in (83741819, 83745022) if w in streams])
    prec_u = unary_union(prec)
    r42 = unary_union([way_line(e) for e in osm.values() if e.get("tags", {}).get("name") == "国道42号"]).buffer(9)
    street_u = unary_union([way_line(e).buffer(3) for e in osm.values() if e.get("tags", {}).get("highway") in
                            ("residential", "unclassified", "service", "tertiary", "secondary", "primary", "living_street")])
    cls = []
    for i, p in enumerate(pts):
        if mm[i]: c = "mountain"
        elif water_u.contains(p): c = "water"
        elif prec_u.contains(p): c = "precinct"
        elif izumo.contains(p): c = "izumo"
        elif r42.contains(p): c = "route42"
        elif bld_u.contains(p): c = "building"
        elif street_u.contains(p): c = "street"
        else: c = "open"
        cls.append(c)
    runs = []
    for d, c in zip(dd, cls):
        if runs and runs[-1][2] == c: runs[-1][1] = d + 1
        else: runs.append([d, d + 1, c])
    d_entr = LineString(leg1).length

    # ------------------------------------------------------------------ alignment test
    sets = {}
    b_, L_ = seg_bearings(brk_in) if not brk_in.is_empty and brk_in.geom_type == "LineString" else (np.array([]), np.array([]))
    if brk_in.geom_type == "MultiLineString":
        bb, LL = zip(*[seg_bearings(g) for g in brk_in.geoms]); b_, L_ = np.concatenate(bb), np.concatenate(LL)
    sets["slope break"] = (b_, L_)
    iw = ichida_in if ichida_in.geom_type == "LineString" else linemerge(ichida_in)
    if iw.coords[0][1] < iw.coords[-1][1]: iw = LineString(list(iw.coords)[::-1])       # north → south
    if iw.geom_type == "LineString": sets["市田川"] = seg_bearings(iw)
    else:
        bb, LL = zip(*[seg_bearings(g) for g in iw.geoms]); sets["市田川"] = (np.concatenate(bb), np.concatenate(LL))
    rs = [seg_bearings(g.intersection(poly)) for _, _, g in roads if g.intersection(poly).geom_type == "LineString"]
    sets["streets"] = (np.concatenate([r[0] for r in rs]), np.concatenate([r[1] for r in rs]))
    pe = [seg_bearings(LineString(list(p.exterior.coords))) for p in prec + [school]]
    sets["precinct and school edges"] = (np.concatenate([r[0] for r in pe]), np.concatenate([r[1] for r in pe]))
    sets["building long axes"] = (np.array([b["axis"] for b in bin_ if b["elong"] >= 1.15]), np.array([b["g"].area for b in bin_ if b["elong"] >= 1.15]))
    align = {}
    for k, (b, w) in sets.items():
        if len(b) == 0: continue
        m180, r180 = axial_stats(b, w, 180)
        m90, r90 = axial_stats(b % 90, w, 90)
        align[k] = {"mean_axis": round(m180, 1), "R_axis": round(r180, 2), "mean_grid": round(m90, 1), "R_grid": round(r90, 2),
                    "n": int(len(b)), "weight": round(float(np.sum(w)), 1)}

    # local test: each building's grid angle against the local slope-break direction, by distance from the break
    band = brk_band if brk_band.geom_type == "MultiLineString" else MultiLineString([brk_band])
    segs = []
    for g in band.geoms:
        c = list(g.coords)
        for a, b in zip(c, c[1:]):
            segs.append((LineString([a, b]), (math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) + 360) % 180))
    from shapely.strtree import STRtree
    tree = STRtree([s for s, _ in segs])
    rows = []
    for b in blds:
        cg = b["g"].centroid
        if not (miny - 150 < cg.y < maxy + 150): continue
        i = tree.nearest(cg); d = segs[i][0].distance(cg)
        # local direction: length-weighted axial mean of break segments within 20 m of the nearest point
        near = [segs[j] for j in tree.query(segs[i][0].buffer(20))]
        ld, _ = axial_stats([a for _, a in near], [s.length for s, _ in near], 180)
        rows.append({"d": d, "grid": b["grid"], "foot": ld % 90, "area": b["g"].area, "in": b["in"], "b": b})
        b["d"] = d; b["foot"] = ld % 90
    bins = [(0, 25), (25, 50), (50, 100), (100, 200), (200, 400)]
    # the town grid: mean grid angle (mod 90) of the buildings 200–800 m from the slope break
    far = [r for r in rows if 200 <= r["d"] < 800]
    grid_town, grid_R = axial_stats([r["grid"] for r in far], [r["area"] for r in far], 90)
    # discriminating test: only buildings where the local foot direction and the town grid differ by ≥ 10°;
    # each building is counted for whichever reference its own grid angle is closer to
    disc = []
    for lo, hi in bins:
        rr = [r for r in rows if lo <= r["d"] < hi and adiff(r["foot"], grid_town, 90) >= 10]
        if len(rr) < 5: continue
        foot_c = sum(1 for r in rr if adiff(r["grid"], r["foot"], 90) < adiff(r["grid"], grid_town, 90))
        # chance level: the same buildings and the same foot directions, paired at random (2,000 shuffles)
        rng = np.random.default_rng(6674); gr = np.array([r["grid"] for r in rr]); ft = np.array([r["foot"] for r in rr])
        def closer(g, f):
            d1 = np.abs((g - f) % 90); d1 = np.minimum(d1, 90 - d1); d2 = np.abs((g - grid_town) % 90); d2 = np.minimum(d2, 90 - d2)
            return (d1 < d2).mean()
        sims = np.array([closer(gr, rng.permutation(ft)) for _ in range(5000)])
        obs = foot_c / len(rr)
        disc.append({"from": lo, "to": hi, "n": len(rr), "follow_foot_pct": round(100 * obs, 1), "chance_pct": round(100 * float(sims.mean()), 1),
                     "p_one_sided": round(float((np.sum(sims >= obs - 1e-12) + 1) / (len(sims) + 1)), 4)})
    decay = []
    for lo, hi in bins:
        rr = [r for r in rows if lo <= r["d"] < hi]
        if not rr: continue
        to_foot = [adiff(r["grid"], r["foot"], 90) for r in rr]
        to_north = [adiff(r["grid"], 0.0, 90) for r in rr]
        decay.append({"from": lo, "to": hi, "n": len(rr),
                      "foot_10": round(100 * np.mean(np.array(to_foot) <= 10), 1), "north_10": round(100 * np.mean(np.array(to_north) <= 10), 1),
                      "median_to_foot": round(float(np.median(to_foot)), 1), "median_to_north": round(float(np.median(to_north)), 1),
                      "foot_dir_mean": round(axial_stats([r["foot"] for r in rr], [1] * len(rr), 90)[0], 1)})
    # stream vs foot: distance of 市田川 from the slope break along its run inside the polygon
    sd = [brk_band.distance(iw.interpolate(t)) for t in np.arange(0, iw.length, 2.0)] if iw.length else []

    # per-building record for the map: which reference each building's own grid follows
    bl = []
    for b in blds:
        if "d" not in b: bcls = "far"
        elif adiff(b["foot"], grid_town, 90) < 10: bcls = "both"
        else: bcls = "foot" if adiff(b["grid"], b["foot"], 90) < adiff(b["grid"], grid_town, 90) else "grid"
        if b.get("d", 1e9) >= 400: bcls = "far"
        bl.append({"ring": [[round(x, 2), round(y, 2)] for x, y in b["g"].exterior.coords] if b["g"].geom_type == "Polygon" else
                   [[round(x, 2), round(y, 2)] for x, y in max(b["g"].geoms, key=lambda q: q.area).exterior.coords],
                   "code": b["code"], "in": b["in"], "d": round(b.get("d", -1), 1), "cls": bcls, "grid": round(b["grid"], 1)})
    # the mountain stream: length and drop from its first mapped point to 市田川
    ms = mstream if mstream.coords[0][1] else streams[499568828]
    if ms.coords[0][0] > ms.coords[-1][0]: ms = LineString(list(ms.coords)[::-1])   # from the mountain (west) down
    def zat(x, y):
        r, c = rc(x, y); return float(z[r, c])
    ms_top, ms_bot = zat(*ms.coords[0]), zat(*ms.coords[-1])
    # the west strip: height gained between the slope break and the polygon's west edge, along east–west rows
    gains = []
    west_edge = poly.exterior.intersection(unary_union(offs).buffer(0.6))
    for yy in np.arange(miny + 5, maxy - 5, 2.0):
        row = LineString([(minx - 5, yy), (maxx + 5, yy)])
        a, b = row.intersection(brk), row.intersection(west_edge)
        if a.is_empty or b.is_empty: continue
        ax = min(g.x for g in getattr(a, "geoms", [a]) if g.geom_type == "Point") if a.geom_type != "LineString" else None
        bx = min(g.x for g in getattr(b, "geoms", [b]) if g.geom_type == "Point") if b.geom_type != "LineString" else None
        if ax is None or bx is None or ax <= bx: continue
        gains.append(zat(bx, yy) - zat(ax + 1.0, yy))
    town = [h for d, h, c in zip(dd, zz, cls) if d > d_entr + 40 and c != "water"]
    extra = {"mstream_top": round(ms_top, 1), "mstream_bot": round(ms_bot, 1), "mstream_len": round(ms.length),
             "strip_gain_med": round(float(np.median(gains)), 1), "strip_gain_max": round(float(np.max(gains)), 1),
             "town_p5": round(float(np.percentile(town, 5)), 1), "town_max": round(float(np.max(town)), 1), "town_min": round(float(np.min(town)), 1),
             "stream_start_to_break": round(brk_band.distance(Point(iw.coords[0])), 1),
             "ch_width_mean": round(ch_width, 1), "mstream_src": mstream_src,
             "ch_entry_to_break": round(brk_band.distance(Point(*P(135.98424, 33.72437))), 1),
             "stream_min_to_break": round(float(np.min(sd)), 1) if sd else None,
             "robust_in": [round(b["g"].area) for b in bin_ if b["code"] in (3102, 3103, 3112)],
             "robust_in_school": sum(1 for b in bin_ if b["code"] in (3102, 3103, 3112) and school.contains(b["g"].centroid)),
             # (whether the residential-inducement area reaches upslope of the foot is measured in 09_export.py: ground.riz)
             "ukishima_bed": round(float(min(h for d, h, c in zip(dd, zz, cls) if c == "water" and d > d_entr + 40)), 1),
             "mountain_run_m": round(max(b for a, b, c in runs if c == "mountain")),
             "channel_cut_m": round(float(np.median(z[inP & ~mountain & ~np.isnan(z)])) - float(np.nanmin(zin)), 1)}
    out = {
        "water_area": [[list(map(lambda q: [round(q[0], 2), round(q[1], 2)], g.exterior.coords))] for g in getattr(WATER, "geoms", [WATER]) if g.geom_type == "Polygon"],
        "water_lines": [[[round(x, 2), round(y, 2)] for x, y in l.coords] for l in getattr(SINGLE, "geoms", [SINGLE]) if l.geom_type == "LineString"],
        "ichida": [[round(x, 2), round(y, 2)] for x, y in ichida.coords],
        "bld": bl, "grid_town_deg": None,
        "poly": [list(map(lambda q: [round(q[0], 2), round(q[1], 2)], poly.exterior.coords))],
        "edges": {"north": list(north.coords), "south": list(south.coords), "east": list(east.coords)},
        "transect": [list(q) for q in tr.coords], "transect_split_m": round(d_entr, 1),
        "profile": [[round(float(d), 1), round(float(h), 2)] for d, h in zip(dd[::2], zz[::2])],
        "profile_runs": [[round(a, 1), round(b, 1), c] for a, b, c in runs],
        "stats": {
            "area_ha": round(area / 1e4, 2), "ns_m": round(maxy - miny), "ew_m": round(maxx - minx),
            "z_min": round(float(np.nanmin(zin)), 1), "z_max": round(float(np.nanmax(zin)), 1), "z_plain_med": round(float(np.median(z[inP & ~mountain & ~np.isnan(z)])), 1),
            "mountain_pct": round(100 * float(m_in.mean()), 1), "plain_level": tj["plain_m"],
            "ichida_m": round(ichida_in.length), "mstream_m": round(mstream_in.length),
            "road_m": round(road_len), "path_m": round(path_len),
            "bld_n": len(bin_), "bld_robust": robust, "bld_cover_pct": round(100 * foot / area, 1),
            "bld_cover_plain_pct": round(100 * foot / (area * (1 - float(m_in.mean()))), 1),
            "bld_median_m2": round(float(np.median([b["g"].area for b in bin_])), 1),
            "school_ha": round(school.intersection(poly).area / 1e4, 2), "precinct_m2": round(sum(p.intersection(poly).area for p in prec)),
            "ts_pct": share(TS), "fl_pct": share(FL), "red_pct": share(RED), "yel_pct": share(YEL), "ls_any_pct": share(RED.union(YEL)),
            "ls_slope_pct": share(SLOPE), "ls_debris_pct": share(DEBRIS),
            "riz_pct": share(RIZ), "uf_pct": share(UF),
            "summit_ground_m": round(float(zz[0]), 1), "entrance_m": round(float(zz[int(d_entr)]), 1), "cityhall_m": round(float(zz[-1]), 1),
            "transect_m": round(tr.length), "stream_to_break_med": round(float(np.median(sd)), 1) if sd else None,
            "stream_to_break_max": round(float(np.max(sd)), 1) if sd else None, **extra,
        },
        "align": align, "decay": decay, "grid_town": round(grid_town, 1), "grid_town_R": round(grid_R, 2), "disc": disc,
        "disc_excess_beyond_25": round(max(d["follow_foot_pct"] - d["chance_pct"] for d in disc if d["from"] >= 25), 1),
    }
    json.dump(out, open("study.json", "w"), ensure_ascii=False, indent=1)
    s = out["stats"]
    print(json.dumps(s, ensure_ascii=False))
    print("align", json.dumps(align, ensure_ascii=False))
    print("decay", json.dumps(decay, ensure_ascii=False))
    print("town grid", round(grid_town, 1), "R", round(grid_R, 2), "discriminating", json.dumps(disc))
    print("runs", [(a, b, c) for a, b, c in out["profile_runs"] if b - a >= 6])


if __name__ == "__main__":
    main()
