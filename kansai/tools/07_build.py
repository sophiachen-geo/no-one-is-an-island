"""Project and simplify all layers into compact SVG path data for kansai/index.html.

CRS: JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674). 1 SVG unit = 100 m.
Run from the scratch work directory after 01-06 (see README.md). Inputs: osm/*.json, ksj/* (A31b-25 flood mesh included),
land.geojson, basin.geojson, munis.geojson, prefs.geojson, dem1.npy, and tsunami2026/*.geojson (tools/tsunami2026, or set
TSUNAMI2026 to their directory).
Output: geo.json  {frame, views, layers, points, stats}
"""
import json, math, re, os, glob
import numpy as np
from shapely.geometry import (shape, mapping, box, Polygon, MultiPolygon, LineString,
                              MultiLineString, Point, GeometryCollection)
from shapely.ops import unary_union, linemerge, transform
from shapely import STRtree
import shapely
from pyproj import Transformer
from scipy.ndimage import gaussian_filter
from skimage import measure

TF = Transformer.from_crs(6668, 6674, always_xy=True).transform   # JGD2011 geographic -> CS VI
BB = (135.25, 33.38, 136.42, 34.45)            # data sheet (lon/lat)
CITY = (135.70, 33.56, 136.08, 33.95)          # fine-detail window
HAZ = (135.84, 33.56, 136.08, 33.82)           # hazard detail window (urban coast)

def proj(g):
    return transform(TF, g)

# sheet frame: projected lon/lat rectangle (densified so the TM curvature is honest)
def densified_box(b, n=60):
    w, s, e, nn = b
    pts = ([(w + (e - w) * i / n, s) for i in range(n)] + [(e, s + (nn - s) * i / n) for i in range(n)] +
           [(e - (e - w) * i / n, nn) for i in range(n)] + [(w, nn - (nn - s) * i / n) for i in range(n)])
    return Polygon(pts)

FRAME_LL = densified_box(BB)
FRAME = proj(FRAME_LL)
X0, Y1 = FRAME.bounds[0], FRAME.bounds[3]
CITY_P = proj(densified_box(CITY, 20))
HAZ_P = proj(densified_box(HAZ, 20))

def sx(x): return (x - X0) / 100.0
def sy(y): return (Y1 - y) / 100.0

def fnum(v):
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    if s.startswith("0."): s = s[1:]
    elif s.startswith("-0."): s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s

def ring_d(coords, prec, close):
    k = 10 ** prec
    pts = [(round(sx(x) * k), round(sy(y) * k)) for x, y in coords]
    out = []
    for p in pts:
        if not out or p != out[-1]: out.append(p)
    if close and len(out) > 1 and out[0] == out[-1]: out = out[:-1]
    if len(out) < 2: return ""
    s = "M" + fnum(out[0][0] / k) + " " + fnum(out[0][1] / k)
    parts = []
    for (ax, ay), (bx, by) in zip(out, out[1:]):
        dx, dy = (bx - ax) / k, (by - ay) / k
        a, b = fnum(dx), fnum(dy)
        parts.append(a + ("" if b.startswith("-") else " ") + b)
    body = "l" + " ".join(parts).replace(" -", "-")
    return s + body + ("z" if close else "")

def to_d(g, prec=1):
    if g is None or g.is_empty: return ""
    if isinstance(g, Polygon):
        return "".join(ring_d(r.coords, prec, True) for r in [g.exterior, *g.interiors])
    if isinstance(g, LineString):
        return ring_d(g.coords, prec, False)
    if hasattr(g, "geoms"):
        return "".join(to_d(x, prec) for x in g.geoms)
    return ""

def polys_only(g):
    if g.is_empty: return g
    if isinstance(g, (Polygon, MultiPolygon)): return g
    return unary_union([x for x in getattr(g, "geoms", []) if isinstance(x, (Polygon, MultiPolygon))])

def lines_only(g):
    if g.is_empty: return g
    if isinstance(g, (LineString, MultiLineString)): return g
    out = []
    for x in getattr(g, "geoms", []):
        if isinstance(x, LineString): out.append(x)
        elif isinstance(x, MultiLineString): out.extend(x.geoms)
    return MultiLineString(out) if out else GeometryCollection()

def drop_small(g, min_area):
    if isinstance(g, Polygon): return g if g.area >= min_area else Polygon()
    return MultiPolygon([p for p in getattr(g, "geoms", []) if p.area >= min_area])

def load_features(fn, filt=lambda p: True, clip=None):
    d = json.load(open(fn, encoding="utf-8"))
    out = []
    for ft in d["features"]:
        if not ft.get("geometry") or not filt(ft["properties"]): continue
        g = shape(ft["geometry"])
        if clip is not None and not g.intersects(clip): continue
        out.append((ft["properties"], g))
    return out

layers, points, stats = {}, [], {}

# ---------------------------------------------------------------- land & coast
land = shape(json.load(open("land.geojson")))
land_p = proj(land).buffer(0)
outer = drop_small(polys_only(land_p.difference(CITY_P).simplify(70)), 60000)
inner = drop_small(polys_only(land_p.intersection(CITY_P).simplify(8)), 3000)
layers["land"] = to_d(outer, 1) + to_d(inner, 1)
cut = FRAME.boundary.buffer(30).union(CITY_P.boundary.buffer(12))
coast_outer = lines_only(outer.boundary.difference(FRAME.boundary.buffer(30)).difference(CITY_P.boundary.buffer(90)))
coast_inner = lines_only(inner.boundary.difference(CITY_P.boundary.buffer(15)))
layers["coast"] = to_d(coast_outer, 1) + to_d(coast_inner, 1)
layers["frame"] = to_d(FRAME.simplify(5), 1)
LAND_FULL = land_p

# ---------------------------------------------------------------- graticule
grat = []
for lon in np.arange(135.25, 136.5, 0.25):
    grat.append(LineString([(lon, 33.38 + i * 0.01) for i in range(108)]))
for lat in np.arange(33.5, 34.45, 0.25):
    grat.append(LineString([(135.25 + i * 0.01, lat) for i in range(118)]))
layers["graticule"] = to_d(lines_only(unary_union([proj(g).intersection(FRAME) for g in grat])), 1)
ticks = []
for lon in np.arange(135.25, 136.5, 0.25):
    x, y = TF(lon, 33.38); ticks.append({"t": f"{int(lon)}°{int(round((lon % 1) * 60)):02d}′E", "x": round(sx(x), 1), "y": round(sy(y), 1), "a": "b"})
for lat in np.arange(33.5, 34.45, 0.25):
    x, y = TF(135.25, lat); ticks.append({"t": f"{int(lat)}°{int(round((lat % 1) * 60)):02d}′N", "x": round(sx(x), 1), "y": round(sy(y), 1), "a": "l"})
stats["ticks"] = ticks

# ---------------------------------------------------------------- terrain contours
dem1 = np.load("dem1.npy")        # 1", origin 35N 135E
def dem_window(lon0, lat0, lon1, lat1, step):
    r0 = int((35.0 - lat1) * 3600); r1 = int((35.0 - lat0) * 3600)
    c0 = int((lon0 - 135.0) * 3600); c1 = int((lon1 - 135.0) * 3600)
    a = dem1[r0:r1:step, c0:c1:step].astype(float)
    return a, r0, c0

def contour_layer(bbox, step, sigma, levels, simp, min_len, clip):
    a, r0, c0 = dem_window(*bbox, step)
    a = gaussian_filter(a, sigma)
    out = {}
    for lv in levels:
        ls = []
        for c in measure.find_contours(a, lv):
            lat = 35.0 - (r0 + c[:, 0] * step) / 3600.0
            lon = 135.0 + (c0 + c[:, 1] * step) / 3600.0
            if len(c) < 4: continue
            g = proj(LineString(np.c_[lon, lat])).simplify(simp)
            if g.length < min_len: continue
            ls.append(g)
        m = unary_union(ls).intersection(clip) if ls else GeometryCollection()
        out[lv] = lines_only(m)
    return out

reg_ct = contour_layer(BB, 6, 2.6, [400, 1000, 1500], 120, 4000, FRAME.difference(CITY_P).intersection(LAND_FULL.buffer(50)))
city_ct = contour_layer(CITY, 2, 1.6, [20, 50, 100, 400, 1000], 14, 500, CITY_P.intersection(LAND_FULL.buffer(20)))
layers["contour_major"] = to_d(lines_only(unary_union([reg_ct[1000], city_ct[1000]])), 1)
layers["contour_minor"] = to_d(lines_only(unary_union([reg_ct[400], reg_ct[1500], city_ct[400], city_ct[100]])), 1)
layers["contour_low"] = to_d(lines_only(unary_union([city_ct[20], city_ct[50]])), 1)

# ---------------------------------------------------------------- admin
munis = {k: shape(v) for k, v in json.load(open("munis.geojson")).items()}
prefs = {k: shape(v) for k, v in json.load(open("prefs.geojson")).items()}
def shared(a, b):
    g = a.boundary.intersection(b.boundary)
    return lines_only(g)
pb = []
names = list(prefs)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        pb.append(shared(prefs[names[i]], prefs[names[j]]))
pref_lines = proj(linemerge(unary_union([g for g in pb if not g.is_empty])))
pref_lines = lines_only(pref_lines.intersection(FRAME))
layers["pref"] = to_d(lines_only(pref_lines.difference(CITY_P).simplify(40)), 1) + to_d(lines_only(pref_lines.intersection(CITY_P).simplify(6)), 1)

# municipal borders inside the sheet (exclude prefecture borders and coast)
mk = [k for k, g in munis.items() if g.intersects(FRAME_LL)]
ml = []
for i in range(len(mk)):
    for j in range(i + 1, len(mk)):
        a, b = munis[mk[i]], munis[mk[j]]
        if a.intersects(b):
            ml.append(shared(a, b))
mun_lines = proj(linemerge(unary_union([g for g in ml if not g.is_empty])))
mun_lines = lines_only(mun_lines.intersection(FRAME).difference(pref_lines.buffer(30)))
layers["muni"] = to_d(lines_only(mun_lines.difference(CITY_P).simplify(90)), 1) + to_d(lines_only(mun_lines.intersection(CITY_P).simplify(8)), 1)

def muni(name, pref=None):
    for k, g in munis.items():
        p, n, c = k.split("|")
        if n == name and (pref is None or p == pref): return g
    raise KeyError(name)

HIG = ["新宮市", "那智勝浦町", "太地町", "古座川町", "北山村", "串本町"]
hig = unary_union([muni(n, "和歌山県") for n in HIG])
hig_p = proj(hig).buffer(0)
layers["higashimuro"] = to_d(drop_small(polys_only(hig_p.simplify(45)), 20000), 1)
shingu_p = proj(muni("新宮市")).buffer(0)
layers["shingu"] = to_d(drop_small(polys_only(shingu_p.simplify(15)), 5000), 1)
kitayama_p = proj(muni("北山村")).buffer(0)
layers["kitayama"] = to_d(polys_only(kitayama_p.simplify(20)), 1)

# ---------------------------------------------------------------- basin
basin = shape(json.load(open("basin.geojson")))
basin_p = proj(basin).buffer(120).buffer(-120).simplify(60)
layers["basin"] = to_d(basin_p, 1)
# basin split by prefecture (for the funnel view)
for key, pn in (("basin_nara", "奈良県"), ("basin_mie", "三重県"), ("basin_wakayama", "和歌山県")):
    layers[key] = to_d(polys_only(basin_p.intersection(proj(prefs[pn]).buffer(0)).simplify(40)), 1)
stats["basin_km2"] = round(proj(basin).area / 1e6, 1)

# ---------------------------------------------------------------- rivers (OSM)
rv = json.load(open("osm/rivers.json"))
MAIN = {"熊野川", "十津川", "北山川", "天ノ川", "天の川"}
main_l, trib_l, other_l = [], [], []
basin_buf = proj(basin).buffer(300)
for el in rv["elements"]:
    if el["type"] != "way" or len(el.get("geometry", [])) < 2: continue
    nm = el.get("tags", {}).get("name", "")
    g = proj(LineString([(p["lon"], p["lat"]) for p in el["geometry"]]))
    if nm in MAIN and g.intersects(basin_buf): main_l.append(g)
    elif g.intersects(basin_buf) and g.within(basin_buf.buffer(200)): trib_l.append(g)
    else: other_l.append(g)
def merge_simplify(ls, s_out, s_in):
    m = linemerge(unary_union(ls)) if ls else GeometryCollection()
    m = lines_only(m.intersection(FRAME))
    return to_d(lines_only(m.difference(CITY_P).simplify(s_out)), 1) + to_d(lines_only(m.intersection(CITY_P).simplify(s_in)), 1)
layers["river_main"] = merge_simplify(main_l, 40, 8)
# prune tiny tributary fragments
trib_m = lines_only(linemerge(unary_union(trib_l)))
trib_keep = [g for g in trib_m.geoms if g.length > 3000]
layers["river_trib"] = merge_simplify(trib_keep, 70, 12)
oth_m = lines_only(linemerge(unary_union(other_l)))
layers["river_other"] = merge_simplify([g for g in oth_m.geoms if g.length > 7000], 100, 15)

# water areas (city window) from OSM
try:
    cw = json.load(open("osm/city_water.json"))
    wp = []
    for el in cw["elements"]:
        if el["type"] == "way" and len(el.get("geometry", [])) > 3:
            c = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if c[0] == c[-1]: wp.append(Polygon(c).buffer(0))
        elif el["type"] == "relation":
            outers = []
            for m in el.get("members", []):
                if m.get("geometry") and m.get("role") == "outer":
                    outers.append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
            from shapely.ops import polygonize
            for pg in polygonize(unary_union(outers)): wp.append(pg)
    W = proj(unary_union(wp)).intersection(CITY_P)
    W = drop_small(polys_only(W.simplify(6)), 2000)
    layers["water"] = to_d(W, 1)
except FileNotFoundError:
    layers["water"] = ""

# ---------------------------------------------------------------- transport
rd = json.load(open("osm/roads.json"))
def roads(pred):
    out = []
    for el in rd["elements"]:
        t = el.get("tags", {})
        if el["type"] == "way" and len(el.get("geometry", [])) > 1 and pred(t):
            out.append(proj(LineString([(p["lon"], p["lat"]) for p in el["geometry"]])))
    return out
refs = lambda t: set((t.get("ref") or "").split(";"))
layers["expressway"] = merge_simplify(roads(lambda t: t.get("highway") == "motorway"), 40, 10)
layers["nr42"] = merge_simplify(roads(lambda t: t.get("highway") == "trunk" and "42" in refs(t)), 40, 10)
layers["nr168"] = merge_simplify(roads(lambda t: t.get("highway") == "trunk" and "168" in refs(t)), 40, 10)
layers["nr_other"] = merge_simplify(roads(lambda t: t.get("highway") == "trunk" and (refs(t) & {"169", "311", "425"}) and not (refs(t) & {"42", "168"})), 45, 10)
try:
    cr = json.load(open("osm/city_roads.json"))
    loc = []
    for el in cr["elements"]:
        if el["type"] == "way" and len(el.get("geometry", [])) > 1:
            loc.append(proj(LineString([(p["lon"], p["lat"]) for p in el["geometry"]])))
    prim = roads(lambda t: t.get("highway") == "primary")
    m = lines_only(linemerge(unary_union(loc + prim)).intersection(CITY_P))
    layers["road_local"] = to_d(lines_only(m.simplify(10)), 1)
except FileNotFoundError:
    layers["road_local"] = ""
ra = json.load(open("osm/rail.json"))
rail = []
for el in ra["elements"]:
    t = el.get("tags", {})
    if el["type"] == "way" and len(el.get("geometry", [])) > 1 and ("紀勢" in (t.get("name", "") + t.get("railway:line", "") + t.get("line", "")) or t.get("operator", "").startswith("西日本旅客鉄道") or t.get("operator", "").startswith("東海旅客鉄道")):
        rail.append(proj(LineString([(p["lon"], p["lat"]) for p in el["geometry"]])))
layers["rail"] = merge_simplify(rail, 40, 8)

# ---------------------------------------------------------------- Kumano Kodo
rt = json.load(open("osm/routes.json"))
kodo = []
for el in rt["elements"]:
    for m in el.get("members", []):
        if m["type"] == "way" and m.get("geometry"):
            kodo.append(proj(LineString([(p["lon"], p["lat"]) for p in m["geometry"]])))
layers["kodo"] = merge_simplify(kodo, 40, 10)
pois = json.load(open("osm/pois.json"))["elements"]
def poi(name):
    for e in pois:
        if e.get("tags", {}).get("name") == name:
            return (e.get("lon") or e["center"]["lon"], e.get("lat") or e["center"]["lat"])
    raise KeyError(name)
# approximate courses (waypoint sequences) for routes only partly mapped in OSM
OKUGAKE = [(135.859, 34.366), poi("青根ヶ峰"), poi("四寸岩山"), poi("大天井ヶ岳"), poi("山上ヶ岳"), poi("大普賢岳"), poi("国見岳"), poi("七曜岳"),
           poi("行者還岳"), poi("弁天の森"), poi("弥山"), poi("八経ヶ岳"), poi("明星ヶ岳"), poi("仏生嶽"), poi("孔雀岳"), poi("釈迦ヶ岳"),
           poi("大日岳"), poi("天狗山"), (135.9004, 34.0774), poi("涅槃岳"), poi("転法輪岳"), (135.9049, 34.0044), poi("笠捨山"),
           (135.8846, 33.9869), (135.862, 33.955), (135.8316, 33.9266), (135.8053, 33.904), (135.785, 33.872), (135.7707, 33.8408)]
ISEJI = [(136.1901, 34.0747), (136.2031, 34.0016), (136.1895, 33.9719), (136.1806, 33.9391), (136.1441, 33.9281), (136.1376, 33.91),
         (136.1181, 33.9022), (136.0987, 33.8897), (136.0934, 33.8798), (136.0856, 33.8762), (136.0625, 33.8401), (136.0552, 33.8277),
         (136.0424, 33.8048), (136.0239, 33.7602), (136.016, 33.737), (135.9963, 33.7398), (135.9837, 33.7323)]
OHECHI = [(135.3845, 33.7329), (135.3873, 33.6759), (135.4578, 33.5854), (135.4957, 33.5468), (135.5757, 33.5153), (135.6033, 33.5098),
          (135.655, 33.5011), (135.6779, 33.4903), (135.7187, 33.488), (135.7817, 33.4756), (135.8209, 33.5193), (135.8683, 33.5365),
          (135.8939, 33.5604), (135.9224, 33.5824), (135.9249, 33.6095), (135.9344, 33.6447), (135.9, 33.662), (135.8903, 33.6685)]
approx = [proj(LineString(OKUGAKE)), proj(LineString(ISEJI)), proj(LineString(OHECHI))]
layers["kodo_approx"] = to_d(MultiLineString([a.simplify(30) for a in approx]), 1)
# the river pilgrimage route: the Kumano River from Hongu Taisha to the mouth (inscribed as part of the
# World Heritage property). OSM names the whole main stem 熊野川 but breaks it near Miyai, so the two
# pieces are joined across the ~0.5 km gap.
kl = [proj(LineString([(p["lon"], p["lat"]) for p in el["geometry"]])) for el in rv["elements"]
      if el["type"] == "way" and el.get("tags", {}).get("name") == "熊野川" and len(el.get("geometry", [])) > 1]
km_ = lines_only(linemerge(unary_union([l for l in kl if l.intersects(basin_buf)])))
parts = list(km_.geoms)
longest = max(parts, key=lambda p: p.length)
hongu = Point(*TF(*poi("熊野本宮大社")))
up = shapely.ops.substring(longest, longest.project(hongu), longest.length)
rest = [p for p in parts if p is not longest]
if rest:
    low = min(rest, key=lambda p: Point(p.coords[0]).distance(Point(up.coords[-1])))
    seg = LineString(list(up.coords) + list(low.coords))
else:
    seg = up
layers["river_route"] = to_d(seg.simplify(30), 1)
stats["river_route_km"] = round(seg.length / 1000, 1)

# ---------------------------------------------------------------- hazards
def union_features(fn, filt, clip_ll, simp, clip_p, min_area):
    fs = load_features(fn, filt, clip_ll)
    gs = [g.buffer(0) for p, g in fs]
    u = unary_union(gs)
    u = proj(u).intersection(clip_p)
    return drop_small(polys_only(u.simplify(simp)), min_area)
# tsunami, maximum class. Shingū and Kihō: the 2026 assumptions, digitised from the prefectures' PDF maps
# (tools/tsunami2026: Wakayama 令和8年 南海トラフ巨大地震; Mie 2026 図面番号22). Elsewhere: MLIT A40, which still holds
# Wakayama's 2013 and Mie's 2015 assumptions. Each source is clipped to the territory it was made for.
import shapefile
TS26 = os.environ.get("TSUNAMI2026", "tsunami2026")
def load_ts26(fn, classes=None):
    return [g.buffer(0) for p, g in load_features(os.path.join(TS26, fn), lambda p: classes is None or p["class"] in classes)]
def load_mie_tsunami(clip_ll):
    sf = shapefile.Reader("ksj/A40-16_24_GML/A40-16_24.shp", encoding="cp932")
    out = []
    minx, miny, maxx, maxy = clip_ll.bounds
    for sr in sf.iterShapeRecords():
        bx = sr.shape.bbox
        if bx[2] < minx or bx[0] > maxx or bx[3] < miny or bx[1] > maxy: continue
        out.append(shape(sr.shape.__geo_interface__).buffer(0))
    return out
FRAME_SOUTH = box(135.25, 33.38, 136.42, 34.12)
ts_w = [g.buffer(0) for p, g in load_features("ksj/A40-16_30_GML/A40-16_30.geojson", clip=FRAME_SOUTH)]
ts_m = load_mie_tsunami(FRAME_SOUTH)
SHINGU_P = proj(muni("新宮市", "和歌山県")).buffer(0); KIHO_P = proj(muni("紀宝町", "三重県")).buffer(0)
TS26_S = proj(unary_union(load_ts26("shingu_r8_max.geojson"))).buffer(0)
TS26_K = proj(unary_union(load_ts26("kiho_mie2026_max.geojson"))).buffer(0)
TS_W = proj(unary_union(ts_w).buffer(0)).intersection(proj(prefs["和歌山県"]).buffer(0)).difference(SHINGU_P).union(TS26_S.intersection(SHINGU_P))
TS_M = proj(unary_union(ts_m).buffer(0)).intersection(proj(prefs["三重県"]).buffer(0)).difference(KIHO_P).union(TS26_K.intersection(KIHO_P))
TS = TS_W.union(TS_M)
stats["tsunami_sources"] = {"2026": ["新宮市 (Wakayama 令和8年, 南海トラフ巨大地震)", "紀宝町 (Mie 2026, 図面番号22)"],
                            "A40": "elsewhere (Wakayama 2013, Mie 2015 assumptions)"}
stats["tsunami2026_ha"] = {"shingu_max": round(TS26_S.intersection(SHINGU_P).area / 1e4, 1), "kiho_max": round(TS26_K.intersection(KIHO_P).area / 1e4, 1)}
TS_region = drop_small(polys_only(TS.difference(HAZ_P).buffer(40).buffer(-40).simplify(70)), 20000)
TS_fine = drop_small(polys_only(TS.intersection(HAZ_P).buffer(6).buffer(-6).simplify(8)), 800)
layers["tsunami"] = to_d(TS_region, 1) + to_d(TS_fine, 1)
# 2026 depth tiers (Shingū + Kihō, maximum class) and Shingū's frequent-earthquake (3連動) inundation, fine window only
def ts26_tier(classes):
    g = unary_union([unary_union([proj(x) for x in load_ts26("shingu_r8_max.geojson", classes)]).intersection(SHINGU_P),
                     unary_union([proj(x) for x in load_ts26("kiho_mie2026_max.geojson", classes)]).intersection(KIHO_P)])
    return drop_small(polys_only(g.buffer(4).buffer(-4).simplify(6)), 300)
layers["ts26_shallow"] = to_d(ts26_tier({1, 2}), 1)          # under 0.5 m
layers["ts26_mid"] = to_d(ts26_tier({3, 4}), 1)              # 0.5–3 m
layers["ts26_deep"] = to_d(ts26_tier({5, 6, 7, 8}), 1)       # 3 m and more
TSF = unary_union([proj(x) for x in load_ts26("shingu_r8_freq.geojson")]).intersection(SHINGU_P)
layers["ts26_freq"] = to_d(drop_small(polys_only(TSF.buffer(4).buffer(-4).simplify(6)), 300), 1)
# river flood: MLIT A31b-25 (10 m mesh; every river with a published map, national and prefectural, merged) —
# maximum assumed (想定最大規模, L2) and planned scale (計画規模, L1)
def a31b(folder, clip_ll=CITY):
    out = []
    for fn in sorted(glob.glob(f"ksj/A31b-25/{folder}/*.shp")):
        for sr in shapefile.Reader(fn[:-4], encoding="cp932").iterShapeRecords():
            b = sr.shape.bbox
            if b[2] < clip_ll[0] or b[0] > clip_ll[2] or b[3] < clip_ll[1] or b[1] > clip_ll[3]: continue
            out.append(shape(sr.shape.__geo_interface__))
    return unary_union(out)
FL = a31b("20_想定最大規模")
FL_p = proj(FL).buffer(0)
layers["flood"] = to_d(drop_small(polys_only(FL_p.intersection(CITY_P).buffer(8).buffer(-8).simplify(9)), 1500), 1)
FL1_p = proj(a31b("10_計画規模")).buffer(0)
layers["flood_l1"] = to_d(drop_small(polys_only(FL1_p.intersection(CITY_P).buffer(8).buffer(-8).simplify(9)), 1500), 1)
# landslide zones (Wakayama + Mie) in the city window
LS_WIN = (135.925, 33.655, 136.045, 33.765)          # yellow zones: urban core only
RED_WIN = (135.865, 33.56, 136.045, 33.765)          # red zones: the whole Shingu-Taiji coast view
LS_CLIP = box(*RED_WIN)
LS_P = proj(densified_box(LS_WIN, 10))
RED_P = proj(densified_box(RED_WIN, 10))
red, yel = [], []
for fn in ("ksj/A33-25_30Polygon.geojson", "ksj/A33-25_24Polygon.geojson"):
    for p, g in load_features(fn, clip=LS_CLIP):
        (red if p["A33_002"] in (2, 4) else yel).append(g.buffer(0))
RED_ALL = proj(unary_union(red)); RED = RED_ALL.intersection(RED_P); YEL = proj(unary_union(yel)).intersection(LS_P)
layers["ls_red"] = to_d(drop_small(polys_only(RED.simplify(8)), 400), 1)
layers["ls_yellow"] = to_d(drop_small(polys_only(YEL.buffer(8).buffer(-8).difference(RED).simplify(8)), 600), 1)

# ---------------------------------------------------------------- location optimisation plan (A55)
rit = load_features("ksj/A55-24_30207_GEOJSON/30207_ritteki.geojson")
RIZ = proj(unary_union([g.buffer(0) for p, g in rit if p["AreaType"] == "居住誘導区域"]))
PLAN = proj(unary_union([g.buffer(0) for p, g in rit if p["AreaType"] == "立地適正化計画区域"]))
UF = [proj(g.buffer(0)) for p, g in rit if p["AreaType"] == "都市機能誘導区域"]
tokei = load_features("ksj/A55-24_30207_GEOJSON/30207_tokei.geojson")
CPA = proj(unary_union([g.buffer(0) for p, g in tokei]))
layers["plan_area"] = to_d(PLAN.simplify(4), 2)
layers["cpa"] = to_d(CPA.simplify(6), 1)
layers["riz"] = to_d(RIZ.simplify(3), 2)
layers["uf"] = to_d(unary_union(UF).simplify(3), 2)
stats["cpa_km2"] = round(CPA.area / 1e6, 2)
stats["plan_km2"] = round(PLAN.area / 1e6, 2)

def pct(a, b): return round(100 * a.intersection(b).area / a.area, 1)
uf_named = {}
for g in UF:
    c = g.centroid
    lon, lat = Transformer.from_crs(6674, 6668, always_xy=True).transform(c.x, c.y)
    key = "centre" if lat > 33.71 else ("koyo_medical" if lon < 135.975 else "miwasaki")
    uf_named[key] = g
stats["overlap"] = {
    "riz": {"km2": round(RIZ.area / 1e6, 2), "tsunami": pct(RIZ, TS), "flood": pct(RIZ, FL_p), "either": pct(RIZ, TS.union(FL_p)), "red": pct(RIZ, RED)},
    **{k: {"km2": round(g.area / 1e6, 2), "tsunami": pct(g, TS), "flood": pct(g, FL_p), "either": pct(g, TS.union(FL_p)), "red": pct(g, RED)} for k, g in uf_named.items()},
}

# ---------------------------------------------------------------- transport exposure (share of line length in tsunami L2, Higashimuro coast)
def km_in(lines_list, area):
    m = unary_union(lines_list)
    return round(m.intersection(area).length / 1000, 1), round(m.length / 1000, 1)
hig_coast = hig_p
stats["exposure"] = {
    "nr42_in_tsunami_km": km_in([l.intersection(hig_coast) for l in roads(lambda t: t.get("highway") == "trunk" and "42" in refs(t))], TS),
    "rail_in_tsunami_km": km_in([l.intersection(hig_coast) for l in rail], TS),
    "expressway_in_tsunami_km": km_in([l.intersection(hig_coast) for l in roads(lambda t: t.get("highway") == "motorway")], TS),
}


# ---------------------------------------------------------------- drive-time from the regional hospital
import heapq
SPEED = {"motorway": 70, "motorway_link": 40, "trunk": 45, "trunk_link": 30, "primary": 35, "secondary": 30, "tertiary": 25}
edges = {}
def add_way(coords, hw):
    v = SPEED.get(hw)
    if not v: return
    pp = [TF(lon, lat) for lon, lat in coords]
    for (a, b) in zip(pp, pp[1:]):
        ka = (round(a[0]), round(a[1])); kb = (round(b[0]), round(b[1]))
        t = math.hypot(b[0] - a[0], b[1] - a[1]) / (v * 1000 / 60)   # minutes
        edges.setdefault(ka, []).append((kb, t)); edges.setdefault(kb, []).append((ka, t))
for el in rd["elements"]:
    if el["type"] == "way" and el.get("geometry"):
        add_way([(p["lon"], p["lat"]) for p in el["geometry"]], el["tags"].get("highway"))
try:
    for el in json.load(open("osm/city_roads.json"))["elements"]:
        if el["type"] == "way" and el.get("geometry"):
            add_way([(p["lon"], p["lat"]) for p in el["geometry"]], el["tags"].get("highway"))
except FileNotFoundError:
    pass
src_ll = poi("新宮市立医療センター"); sxy = TF(*src_ll)
start = min(edges, key=lambda k: math.hypot(k[0] - sxy[0], k[1] - sxy[1]))
dist = {start: 0.0}; pq = [(0.0, start)]
while pq:
    d, u = heapq.heappop(pq)
    if d > dist.get(u, 1e9) or d > 130: continue
    for v, t in edges[u]:
        nd = d + t
        if nd < dist.get(v, 1e9): dist[v] = nd; heapq.heappush(pq, (nd, v))
iso = {}
# raster the reached road network on a 250 m grid, grow by the 1.2 km catchment, contour back to polygons
from scipy.ndimage import binary_dilation
CELL = 250.0
fx0, fy0, fx1, fy1 = FRAME.bounds
nx, ny = int((fx1 - fx0) / CELL) + 1, int((fy1 - fy0) / CELL) + 1
tgrid = np.full((ny, nx), np.inf)
for u, lst in edges.items():
    du = dist.get(u)
    if du is None: continue
    for v, t in lst:
        dv = dist.get(v)
        if dv is None: continue
        n = int(math.hypot(v[0] - u[0], v[1] - u[1]) / (CELL / 2)) + 1
        for k in range(0, n + 1):
            f = k / n; x = u[0] + (v[0] - u[0]) * f; y = u[1] + (v[1] - u[1]) * f; dm = du + (dv - du) * f
            i, j = int((fy1 - y) / CELL), int((x - fx0) / CELL)
            if 0 <= i < ny and 0 <= j < nx and dm < tgrid[i, j]: tgrid[i, j] = dm
yy, xx = np.mgrid[-5:6, -5:6]
disk = (xx ** 2 + yy ** 2) <= 4.8 ** 2
for T in (30, 60, 90):
    m = binary_dilation(tgrid <= T, structure=disk)
    m = gaussian_filter(m.astype(float), 1.0)
    rings = []
    for c in measure.find_contours(np.pad(m, 1), 0.5):
        xs = fx0 + (c[:, 1] - 1 + 0.5) * CELL; ys = fy1 - (c[:, 0] - 1 + 0.5) * CELL
        if len(c) > 4: rings.append(Polygon(np.c_[xs, ys]).buffer(0))
    rings.sort(key=lambda p: -p.area)
    acc_poly = Polygon()
    for p in rings:
        acc_poly = acc_poly.symmetric_difference(p)
    iso[T] = drop_small(polys_only(acc_poly.intersection(LAND_FULL).simplify(120)), 2e6)
    layers[f"iso{T}"] = to_d(iso[T], 1)
stats["iso60_share"] = {}
for k, g in munis.items():
    pn, n, c = k.split("|")
    gp = proj(g).buffer(0)
    if gp.intersects(iso[60]):
        sh = gp.intersection(iso[60]).area / gp.area
        if sh > 0.02: stats["iso60_share"][n] = round(100 * sh)

# ---------------------------------------------------------------- named points (lon/lat -> svg)
P = {
 "shingu": (135.9925, 33.7241), "station": (135.9941, 33.7251), "cityhall": (135.9925, 33.7241), "medical": (135.9641, 33.6868),
 "hayatama": (135.9837, 33.7323), "kamikura": (135.9828, 33.7222), "hongu": (135.7737, 33.8404), "nachi": (135.8903, 33.6685),
 "miwasaki": (135.9848, 33.6894), "kiisano": (135.9704, 33.6797), "ukui": (135.9723, 33.6625), "katsuura": (135.9416, 33.6281),
 "nachikatsuura": (135.941, 33.626), "taiji": (135.9439, 33.5941), "kushimoto": (135.7817, 33.4756), "kozagawa": (135.8148, 33.5319),
 "koza": (135.8209, 33.5193), "kitayama": (135.9691, 33.9321), "kiho": (136.0096, 33.7338), "udono": (136.016, 33.737),
 "narukawa": (135.9963, 33.7398), "ida": (136.0239, 33.7602), "mihama": (136.0488, 33.8143), "kumano": (136.1004, 33.8885),
 "owase": (136.191, 34.0708), "hongu_office": (135.7731, 33.8382), "totsukawa": (135.7925, 33.9885), "kamikitayama": (136.0002, 34.1343),
 "shimokitayama": (135.9551, 34.005), "tenkawa": (135.8553, 34.2419), "nosegawa": (135.633, 34.1662), "gojo": (135.6956, 34.3564),
 "tanabe": (135.3889, 33.7291), "koyasan": (135.5866, 34.2161), "yoshino": (135.8575, 34.396), "hakkyo": (135.9075, 34.1736),
 "odaigahara": (136.1092, 34.1852), "shionomisaki": (135.7663, 33.4493), "hitari": (135.8707, 33.8052), "takata": (135.9072, 33.7393),
 "koguchi": (135.8418, 33.7587), "oga": (135.9296, 33.7374), "hachibuse": (135.9634, 33.6851), "sano": (135.9681, 33.6867),
 "ukijima": (135.9907, 33.7259), "funada": (135.9792, 33.7448), "minamihizue": (135.9666, 33.721), "atawa": (136.037, 33.801),
 "dam_ikehara": (135.9704, 34.0474), "dam_kazeya": (135.7881, 34.0444), "dam_futatsuno": (135.7829, 33.9092), "dam_nanairo": (135.9141, 33.8716),
 "dam_komori": (135.9279, 33.9347), "dam_saruya": (135.7413, 34.1793), "dam_sakamoto": (136.0504, 34.0907), "dam_asahi": (135.8115, 34.1216),
 "dam_seto": (135.8239, 34.1281), "sabo_office": (135.7276, 34.3811), "kodo_hongu_mouth": (135.9900, 33.7300),
 "uf_centre": None, "uf_koyo": None, "uf_miwasaki": None,
}
pts = {}
for k, ll in P.items():
    if ll is None: continue
    x, y = TF(*ll); pts[k] = [round(sx(x), 2), round(sy(y), 2)]
for key, g in uf_named.items():
    c = g.representative_point(); pts["uf_" + {"centre": "centre", "koyo_medical": "koyo", "miwasaki": "miwasaki"}[key]] = [round(sx(c.x), 2), round(sy(c.y), 2)]

# ---------------------------------------------------------------- views (lon/lat boxes -> svg units)
def vbox(w, s, e, n):
    g = proj(densified_box((w, s, e, n), 8))
    a, b, c, d = g.bounds
    return [round(sx(a), 1), round(sy(d), 1), round(sx(c), 1), round(sy(b), 1)]
views = {
    "region": vbox(135.30, 33.40, 136.38, 34.43),
    "basin": vbox(135.50, 33.66, 136.20, 34.33),
    "higashimuro": vbox(135.60, 33.41, 136.14, 34.02),
    "city": vbox(135.71, 33.64, 136.05, 33.93),
    "core": vbox(135.945, 33.672, 136.025, 33.745),
    "mouth": vbox(135.93, 33.69, 136.07, 33.79),
    "coast": vbox(135.87, 33.57, 136.05, 33.75),
}
frame_svg = [round(sx(FRAME.bounds[0]), 1), round(sy(FRAME.bounds[3]), 1), round(sx(FRAME.bounds[2]), 1), round(sy(FRAME.bounds[1]), 1)]

def pt(lon, lat):
    x, y = TF(lon, lat); return [round(sx(x), 2), round(sy(y), 2)]
json.dump({"frame": frame_svg, "views": views, "layers": layers, "stats": stats, "pts": pts},
          open("geo.json", "w"), ensure_ascii=False)
sizes = sorted(((len(v), k) for k, v in layers.items()), reverse=True)
print("total KB", round(sum(s for s, k in sizes) / 1024, 1))
for s, k in sizes: print(f"  {k:16s} {s/1024:8.1f} KB")
print(json.dumps(stats, ensure_ascii=False, indent=1)[:3000])
