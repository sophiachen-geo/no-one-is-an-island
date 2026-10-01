"""Round-3 additions to geo.json: per-level micro-relief contours, contour labels, extra points,
and (when their inputs exist) morphology layers and building-exposure statistics.

Run from the scratch work directory after 16_extras.py, then 09_inject.py:
    python3 $T/17_round3.py      # reads geo.json, ichida.json, dem1.npy, land.geojson [, morph/*.geojson]
Contour lines are recomputed with exactly the parameters of 07_build.py, so every label sits on a line
the page draws, and each label carries the level it names.
"""
import json, math, os
import numpy as np
from shapely.geometry import shape, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection, Point
from shapely.ops import unary_union, transform
from pyproj import Transformer
from scipy.ndimage import gaussian_filter
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
TF = Transformer.from_crs(6668, 6674, always_xy=True).transform
BB = (135.25, 33.38, 136.42, 34.45)
CITY = (135.70, 33.56, 136.08, 33.95)


def proj(geom):
    return transform(TF, geom)


def densified_box(b, n=60):
    w, s, e, nn = b
    pts = ([(w + (e - w) * i / n, s) for i in range(n)] + [(e, s + (nn - s) * i / n) for i in range(n)] +
           [(e - (e - w) * i / n, nn) for i in range(n)] + [(w, nn - (nn - s) * i / n) for i in range(n)])
    return Polygon(pts)


FRAME = proj(densified_box(BB))
X0, Y1 = FRAME.bounds[0], FRAME.bounds[3]
CITY_P = proj(densified_box(CITY, 20))


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
        a, b = fnum((bx - ax) / k), fnum((by - ay) / k)
        parts.append(a + ("" if b.startswith("-") else " ") + b)
    return s + "l" + " ".join(parts).replace(" -", "-") + ("z" if close else "")


def to_d(geom, prec=1):
    if geom is None or geom.is_empty: return ""
    if isinstance(geom, Polygon):
        return "".join(ring_d(r.coords, prec, True) for r in [geom.exterior, *geom.interiors])
    if isinstance(geom, LineString):
        return ring_d(geom.coords, prec, False)
    if hasattr(geom, "geoms"):
        return "".join(to_d(x, prec) for x in geom.geoms)
    return ""


def lines_only(geom):
    if geom.is_empty: return geom
    if isinstance(geom, (LineString, MultiLineString)): return geom
    out = []
    for x in getattr(geom, "geoms", []):
        if isinstance(x, LineString): out.append(x)
        elif isinstance(x, MultiLineString): out.extend(x.geoms)
    return MultiLineString(out) if out else GeometryCollection()


def parts(geom):
    if geom is None or geom.is_empty: return []
    return list(geom.geoms) if hasattr(geom, "geoms") else [geom]


g = json.load(open("geo.json"))
L, S = g["layers"], g["stats"]

# ---------------------------------------------------------------- micro relief: one layer per level
ic = json.load(open("ichida.json"))
micro = ic["micro"]
MICRO = (3, 5, 7, 10, 20, 40)
micro_geo = {}
for k in MICRO:
    geo = micro.get(str(k))
    micro_geo[k] = proj(shape(geo)) if geo else GeometryCollection()
    L[f"micro_{k}"] = to_d(micro_geo[k], 2)
L.pop("micro_low", None); L.pop("micro_high", None)   # the page rebuilds these two names as aliases of the levels

# ---------------------------------------------------------------- terrain contours, recomputed level by level (07_build.py parameters)
dem1 = np.load("dem1.npy")
LAND_FULL = proj(shape(json.load(open("land.geojson")))).buffer(0)


def contour_layer(bbox, step, sigma, levels, simp, min_len, clip):
    lon0, lat0, lon1, lat1 = bbox
    r0 = int((35.0 - lat1) * 3600); c0 = int((lon0 - 135.0) * 3600)
    a = gaussian_filter(dem1[r0:int((35.0 - lat0) * 3600):step, c0:int((lon1 - 135.0) * 3600):step].astype(float), sigma)
    out = {}
    for lv in levels:
        ls = []
        for c in measure.find_contours(a, lv):
            lat = 35.0 - (r0 + c[:, 0] * step) / 3600.0
            lon = 135.0 + (c0 + c[:, 1] * step) / 3600.0
            if len(c) < 4: continue
            ln = proj(LineString(np.c_[lon, lat])).simplify(simp)
            if ln.length < min_len: continue
            ls.append(ln)
        m = unary_union(ls).intersection(clip) if ls else GeometryCollection()
        out[lv] = lines_only(m)
    return out


reg_ct = contour_layer(BB, 6, 2.6, [400, 1000, 1500], 120, 4000, FRAME.difference(CITY_P).intersection(LAND_FULL.buffer(50)))
city_ct = contour_layer(CITY, 2, 1.6, [20, 50, 100, 400, 1000], 14, 500, CITY_P.intersection(LAND_FULL.buffer(20)))
# the page's layers are unions of these; rebuilding them proves the labels describe the drawn lines
check = {
    "contour_major": to_d(lines_only(unary_union([reg_ct[1000], city_ct[1000]])), 1),
    "contour_minor": to_d(lines_only(unary_union([reg_ct[400], reg_ct[1500], city_ct[400], city_ct[100]])), 1),
    "contour_low": to_d(lines_only(unary_union([city_ct[20], city_ct[50]])), 1),
}
for k, d in check.items():
    print(f"{k}: rebuilt {'identical' if d == L[k] else 'DIFFERENT (labels may drift)'}")


def label_points(geom, spacing, min_len, half):
    """Label anchors along each line: evenly spaced, only where the line is nearly straight over ±half metres.
    Returns [x, y, angle°] in page units, angle kept upright (−90…90)."""
    out = []
    for ln in parts(geom):
        if not isinstance(ln, LineString) or ln.length < min_len: continue
        n = max(1, int(ln.length // spacing))
        for i in range(n):
            d = (i + 0.5) * ln.length / n
            a, b, p = ln.interpolate(max(0.0, d - half)), ln.interpolate(min(ln.length, d + half)), ln.interpolate(d)
            if a.distance(b) < 1.7 * half: continue          # too curved for a readable label
            ang = math.degrees(math.atan2(-(b.y - a.y), b.x - a.x))
            if ang > 90: ang -= 180
            if ang <= -90: ang += 180
            out.append([round(sx(p.x), 2), round(sy(p.y), 2), round(ang, 1)])
    return out


CL = {"micro": [], "city": [], "region": []}
for k in MICRO:
    CL["micro"] += [p + [k] for p in label_points(micro_geo[k], 450, 220, 35)]
for lv in (20, 50, 100, 400, 1000):
    CL["city"] += [p + [lv] for p in label_points(city_ct[lv], 3500, 1800, 260)]
for lv in (400, 1000, 1500):
    CL["region"] += [p + [lv] for p in label_points(reg_ct[lv], 11000, 6000, 900)]
g["clabels"] = CL
print("contour labels:", {k: len(v) for k, v in CL.items()})

# ---------------------------------------------------------------- extra points (sourced in kansai/qa/points.toml)
p3 = os.path.join(HERE, "pts3.json")
if os.path.exists(p3):
    for k, (lon, lat) in json.load(open(p3)).items():
        X, Y = TF(lon, lat); g["pts"][k] = [round(sx(X), 2), round(sy(Y), 2)]

# ---------------------------------------------------------------- morphology: forest, natural-park zones, peaks (morph/, see README)
if os.path.exists("morph/forest.geojson"):
    fo = unary_union([proj(shape(f["geometry"])) for f in json.load(open("morph/forest.geojson"))["features"]]).buffer(0)
    L["forest"] = to_d(fo.simplify(120), 1)
    S["forest_share"] = json.load(open("morph/forest.geojson"))["features"][0]["properties"]["forest_share"]   # from the raw 100 m cells, not the generalised outline
    zones = {f["properties"].get("zone_code"): proj(shape(f["geometry"])).buffer(0) for f in json.load(open("morph/protected.geojson"))["features"] if f["properties"].get("zone_code")}
    if 11 in zones: L["park"] = to_d(zones[11].simplify(150), 1)
    if 13 in zones: L["park_sp"] = to_d(zones[13].simplify(60), 1)
    WANT = {"八経ヶ岳": "Hakkyō", "釈迦ヶ岳": "Shaka", "山上ヶ岳": "Sanjō", "日出ケ岳": "Hinode (Ōdaigahara)", "七面山": "Shichimen", "護摩壇山": "Gomadan",
            "笠捨山": "Kasasute", "伯母子岳": "Obako", "冷水山": "Hiyamizu", "大塔山": "Ōtō", "法師山": "Hōshi", "玉置山": "Tamaki", "子ノ泊山": "Nenotomari", "権現山": "Gongen (Chihogamine)"}
    pk = []
    for f in json.load(open("morph/peaks.geojson"))["features"]:
        pr = f["properties"]; nm = pr.get("name"); ele = pr.get("ele")
        if nm not in WANT or ele is None: continue
        if nm == "玉置山" and ele < 1000: continue          # a second, lower node with the same name
        lon, lat = f["geometry"]["coordinates"]; X, Y = TF(lon, lat)
        pk.append([round(sx(X), 2), round(sy(Y), 2), nm, WANT[nm], int(round(ele)), round(lon, 5), round(lat, 5)])
    g["peaks"] = sorted(pk, key=lambda q: -q[4])
    print("forest", round(len(L["forest"]) / 1024), "KB; park", round(len(L.get("park", "")) / 1024), "KB; peaks", len(pk))

# ---------------------------------------------------------------- building exposure (GSI 最適化ベクトルタイル → morph/buildings.geojson)
# Each footprint is classified by a point inside it, tested against the hazard layers exactly as the page draws
# them (even-odd, page units), and only buildings inside Shingū City count. Output: buildings_page.json, which
# the page loads on the steps that show exposure and which the QA gate re-counts.
if os.path.exists("morph/buildings.geojson"):
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "qa"))
    from geomfast import Region
    TS, FLK, FLI, CITYR = Region(L["tsunami"]), Region(L["flood"]), Region(L["flood_ichida"]), Region(L["shingu"])
    cls = {"dry": [], "fl": [], "ts": [], "both": []}; cent = []
    for f in json.load(open("morph/buildings.geojson"))["features"]:
        geom = proj(shape(f["geometry"])).buffer(0)
        if geom.is_empty: continue
        rp = geom.representative_point(); x, y = round(sx(rp.x), 3), round(sy(rp.y), 3)   # classify the stored point, so a re-count agrees exactly
        if not CITYR.contains(x, y): continue
        t = TS.contains(x, y); fl = FLK.contains(x, y) or FLI.contains(x, y)
        k = "both" if (t and fl) else "ts" if t else "fl" if fl else "dry"
        cls[k].append(geom.simplify(0.6)); cent.append([round(x, 3), round(y, 3)])
    counts = {k: len(v) for k, v in cls.items()}; counts["total"] = len(cent)
    counts["tsunami"] = counts["ts"] + counts["both"]; counts["flood"] = counts["fl"] + counts["both"]; counts["either"] = counts["total"] - counts["dry"]
    S["buildings"] = counts
    out = {"source": "国土地理院最適化ベクトルタイル (GSI optimised vector tiles, building layer, z16), processed: classified against the page's hazard layers",
           "counts": counts, "paths": {k: to_d(MultiPolygon([q for g0 in v for q in parts(g0) if isinstance(q, Polygon)]), 2) for k, v in cls.items()},
           "cent": [c for xy in cent for c in xy]}
    json.dump(out, open("buildings_page.json", "w"), separators=(",", ":"))
    print("buildings:", counts, round(os.path.getsize("buildings_page.json") / 1024), "KB")

# ---------------------------------------------------------------- services (国土数値情報) and road names (OSM, fac/)
# Shingū City's services from MLIT's national layers rather than OpenStreetMap: hospitals and clinics (P04, 2020; dental
# clinics left out), the city hall, branch offices and the Kumanogawa administrative bureau (P05, 2022), schools from
# primary to high school (P29, 2023), care homes and other facilities where people stay overnight (P14, 2023), fire and
# police stations (P17, P18, 2012, non-commercial). 新宮警察署 moved in March 2017 to 新宮2330-9 (Wakayama Prefectural
# Police); its 2012 point is replaced by the new site.
import zipfile, io
def ksj_points(zf, shp_hint=None):
    z = zipfile.ZipFile(zf); names = z.namelist(); gj = [n for n in names if n.endswith(".geojson")]
    if gj:
        for ft in json.loads(z.read(gj[0]).decode("utf-8"))["features"]:
            yield ft["properties"], ft["geometry"]["coordinates"]
        return
    import shapefile
    shp = [n for n in names if n.endswith(".shp") and (shp_hint is None or shp_hint in n)][0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(shp + ".shp")), dbf=io.BytesIO(z.read(shp + ".dbf")), shx=io.BytesIO(z.read(shp + ".shx")), encoding="cp932")
    flds = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        yield dict(zip(flds, sr.record)), sr.shape.points[0]
if os.path.exists("ksj/P04-20_30_GML.zip"):
    from shapely.geometry import Point as _Pt
    from shapely.prepared import prep as _prep
    CITY_LL = _prep(shape(json.load(open("munis.geojson"))["和歌山県|新宮市|30207"]).buffer(0))
    CARE = {"0201", "0202", "0205", "0301", "0502", "0507", "0508", "0511", "9907", "9910"}
    MOVED = {"新宮警察署": (135.9902975, 33.7041666)}          # 新宮市新宮2330-9 since March 2017
    rows = []
    for p, (lo, la) in ksj_points("ksj/P04-20_30_GML.zip"):
        if p["P04_001"] in (1, 2): rows.append(("med", p["P04_002"], lo, la, "国土数値情報 P04 (2020)"))
    for p, (lo, la) in ksj_points("ksj/P05-22_30_GML.zip"):
        if str(p["P05_002"]) in ("1", "2", "3"): rows.append(("admin", p["P05_003"], lo, la, "国土数値情報 P05 (2022)"))
    for p, (lo, la) in ksj_points("ksj/P29-23_30_GML.zip"):
        if str(p["P29_003"]) in ("16001", "16002", "16003", "16004", "16012", "16013") and str(p.get("P29_007")) != "2":   # 2 = 休校中
            rows.append(("school", p["P29_004"], lo, la, "国土数値情報 P29 (2023)"))
    for p, (lo, la) in ksj_points("ksj/P14-23_30_GML.zip"):
        if str(p["P14_006"]) in CARE: rows.append(("care", p["P14_008"], lo, la, "国土数値情報 P14 (2023)"))
    for zf, hint, key in (("ksj/P17-12_30_GML.zip", "FireStation.", "P17_001"), ("ksj/P18-12_30_GML.zip", "PoliceStation.", "P18_001")):
        for p, (lo, la) in ksj_points(zf, hint):
            nm = p[key]; lo, la = MOVED.get(nm, (lo, la))
            rows.append(("safety", nm, lo, la, "国土数値情報 " + zf[4:7] + " (2012)" + (", moved 2017" if nm in MOVED else "")))
    fac, seen = [], set()
    for cat, name, lo, la, src in rows:
        if not CITY_LL.contains(_Pt(lo, la)): continue
        X, Y = TF(lo, la); key = (cat, round(X / 30), round(Y / 30))
        if key in seen: continue                     # two records at one place (a fire HQ and its station)
        seen.add(key); fac.append([round(sx(X), 2), round(sy(Y), 2), cat, name, src])
    g["fac"] = fac
    print("facilities:", {k: sum(1 for f in fac if f[2] == k) for k in sorted(set(f[2] for f in fac))})
if os.path.exists("fac/roads_osm.json"):
    from shapely.ops import linemerge
    LABEL = {"168": "Route 168", "42": "Route 42", "169": "Route 169", "311": "Route 311", "44": "Pref. road 44", "230": "Pref. road 230", "229": "Pref. road 229", "45": "Pref. road 45"}
    NATIONAL = {"168", "42", "169", "311"}
    by = {}
    for e in json.load(open("fac/roads_osm.json"))["elements"]:
        t = e.get("tags", {}); ref = (t.get("ref") or "").split(";")[0]
        if ref.startswith("E") or ref not in LABEL or "geometry" not in e: continue
        if ref not in NATIONAL and t.get("highway") not in ("secondary", "tertiary", "primary"): continue
        by.setdefault(ref, []).append(proj(LineString([(p["lon"], p["lat"]) for p in e["geometry"]])))
    rl = []
    for ref, ls in by.items():
        m = linemerge(unary_union(ls))
        for ln in parts(m):
            if ln.length < 1500: continue
            n = max(1, int(ln.length // 7000))
            for i in range(n):
                d = (i + 0.5) * ln.length / n
                a, b, p = ln.interpolate(max(0, d - 250)), ln.interpolate(min(ln.length, d + 250)), ln.interpolate(d)
                ang = math.degrees(math.atan2(-(b.y - a.y), b.x - a.x))
                if ang > 90: ang -= 180
                if ang <= -90: ang += 180
                rl.append([round(sx(p.x), 2), round(sy(p.y), 2), round(ang, 1), LABEL[ref], 1 if ref in NATIONAL else 0])
    g["roadlabels"] = rl
    print("road labels:", len(rl))

json.dump(g, open("geo.json", "w"), ensure_ascii=False)
print("layers", len(L), "pts", len(g["pts"]), "size", round(len(json.dumps(g, ensure_ascii=False)) / 1024), "KB")
