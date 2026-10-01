"""Kamikura micro-study, step 9 (last): write the page's data and the GIS downloads.

Reads (work dir): study.json (03), terrain.npz / terrain.json (02), terrain_plus.npz / terrain_audit.json (05),
foot.json (06), parcels.json (07), align.json / walls.json / backs.json (08), osm.json, ../ksj hazard layers.
Writes into the repository (pass its kansai/ folder as the only argument):
  data/kamikura.js            window.__KMK = {...}: layers as SVG paths in page units (1 unit = 100 m, the page's
                              JGD2011 / CS VI frame), labels, the profile, statistics, the alignment test
  data/kamikura_relief.jpg    1 m relief (multi-directional hill shading over a height tint), one pixel per metre
  data/kamikura_{elev,slope,lrm,curv}.jpg   the other ground layers on the same 1 m grid: height, slope, local
                              relief and profile curvature (each over a faint hill shading)
  data/kamikura_study.geojson study area, its four edges with their rules, the slope break, the transect (WGS84)
  data/kamikura_study.kml     the same for Google Earth / My Maps
"""
import json, math, sys, os
import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage as ndi
from skimage import measure
from shapely import contains_xy
from shapely.geometry import shape, Polygon, LineString, MultiLineString, Point, box, mapping
from shapely.ops import unary_union, transform

O = (-69782.048, -171691.754)            # the page's origin (G.origin): page = ((E − O0)/100, (O1 − N)/100)
LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
P2LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)
KSJ = "../ksj"


def pg(x, y): return ((x - O[0]) / 100.0, (O[1] - y) / 100.0)


def path(lines, closed=False, nd=3):
    """SVG path in page units; relative moves keep it short (3 decimals = 0.1 m)."""
    out = []
    for L in lines:
        pts = [pg(x, y) for x, y in L]
        if len(pts) < 2: continue
        q = [(round(px, nd), round(py, nd)) for px, py in pts]
        s = f"M{q[0][0]} {q[0][1]}"
        for (ax, ay), (bx, by) in zip(q, q[1:]):
            dx, dy = round(bx - ax, nd), round(by - ay, nd)
            if dx == 0 and dy == 0: continue
            s += f"l{dx:g} {dy:g}".replace(" -", "-")
        out.append(s + ("z" if closed else ""))
    return "".join(out)


def geoms_lines(g):
    if g.is_empty: return []
    if g.geom_type == "LineString": return [list(g.coords)]
    if g.geom_type in ("MultiLineString", "GeometryCollection"): return [l for x in g.geoms for l in geoms_lines(x)]
    if g.geom_type == "Polygon": return [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
    if g.geom_type == "MultiPolygon": return [l for x in g.geoms for l in geoms_lines(x)]
    return []


def proj(g): return transform(lambda x, y, z=None: LL2P.transform(x, y), g)


def relief(z, out):
    """Multi-directional hill shading on a soft height tint — 1 px = 1 m."""
    zz = np.where(np.isnan(z), np.nanmin(z), z).astype(np.float64)
    zs = ndi.gaussian_filter(zz, 0.7)
    gy, gx = np.gradient(zs)
    gy = -gy                                                   # rows run south
    slope = np.arctan(np.hypot(gx, gy) * 1.6)
    aspect = np.arctan2(-gx, gy)
    shade = np.zeros_like(zs)
    for az, w in ((315, .5), (270, .2), (0, .2), (225, .1)):
        a = math.radians(az); alt = math.radians(42)
        shade += w * (math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(a - aspect))
    shade = np.clip(shade, 0, 1)
    t = np.clip((zs - 2) / 60, 0, 1) ** 0.6                    # height tint: plain cream → slope warm grey-green
    lo, hi = np.array([243, 238, 228]), np.array([196, 200, 178])
    base = lo[None, None, :] * (1 - t[..., None]) + hi[None, None, :] * t[..., None]
    k = 0.42 + 0.68 * shade[..., None]
    img = np.clip(base * k, 0, 255).astype(np.uint8)
    img[np.isnan(z)] = (236, 233, 226)
    Image.fromarray(img).save(out, quality=84, optimize=True, progressive=True)


def _shade(z):
    zz = np.where(np.isnan(z), np.nanmin(z), z).astype(np.float64)
    gy, gx = np.gradient(ndi.gaussian_filter(zz, 0.8)); gy = -gy
    slope = np.arctan(np.hypot(gx, gy) * 1.6); aspect = np.arctan2(-gx, gy); sh = np.zeros_like(zz)
    for az, w in ((315, .5), (270, .2), (0, .2), (225, .1)):
        a = math.radians(az); alt = math.radians(42)
        sh += w * (math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(a - aspect))
    return np.clip(sh, 0, 1)


def _ramp(v, stops):
    vs = np.array([q[0] for q in stops], float); cs = np.array([q[1] for q in stops], float)
    v = np.clip(np.nan_to_num(v, nan=vs[0]), vs[0], vs[-1]); out = np.empty(v.shape + (3,))
    for k in range(3): out[..., k] = np.interp(v, vs, cs[:, k])
    return out


# value → colour stops for the ground layers (also sent to the page for their legends)
GROUND = {
    "elev": {"label": "height", "unit": "m", "ticks": [2, 6, 10, 25, 100, 250],
             "stops": [(2, (36, 86, 117)), (4, (64, 133, 141)), (6, (124, 176, 150)), (8, (186, 206, 158)), (10, (229, 226, 178)),
                       (15, (238, 212, 160)), (25, (224, 186, 136)), (50, (198, 152, 108)), (100, (160, 118, 88)), (250, (116, 90, 80))]},
    "slope": {"label": "slope", "unit": "°", "ticks": [0, 3, 8, 15, 30, 45, 70],
              "stops": [(0, (246, 241, 231)), (3, (241, 229, 200)), (8, (233, 201, 150)), (15, (215, 151, 100)), (30, (177, 84, 64)),
                        (45, (120, 40, 50)), (70, (70, 22, 40))]},
    "lrm": {"label": "local relief: ground above (+) or below (−) its 20 m surroundings", "unit": "m", "ticks": [-2.5, -1, 0, 1, 2.5],
            "stops": [(-2.5, (33, 102, 172)), (-1, (146, 197, 222)), (0, (247, 247, 247)), (1, (244, 165, 130)), (2.5, (178, 24, 43))]},
    "curv": {"label": "profile curvature: concave (foot) ← → convex (shoulder, wall top)", "unit": "1/m", "ticks": [-0.08, 0, 0.08],
             "stops": [(-0.08, (1, 102, 94)), (-0.03, (128, 205, 193)), (0, (245, 245, 245)), (0.03, (223, 194, 125)), (0.08, (140, 81, 10))]},
}


def ground_images(z, tp, repo):
    """The four extra ground layers as JPEGs on the relief's grid (1 px = 1 m)."""
    sh = _shade(z)
    src = {"elev": z, "slope": None, "lrm": tp["lrm"], "curv": tp["prof"]}
    zz = np.where(np.isnan(z), np.nanmin(z), z)
    gy, gx = np.gradient(ndi.gaussian_filter(zz, 1.0)); src["slope"] = np.degrees(np.arctan(np.hypot(gx, gy)))
    lift = {"elev": (0.70, 0.36), "slope": (0.82, 0.22), "lrm": (0.78, 0.26), "curv": (0.84, 0.2)}
    out = {}
    for k, spec in GROUND.items():
        col = _ramp(src[k], spec["stops"]) * (lift[k][0] + lift[k][1] * sh)[..., None]
        img = np.clip(col, 0, 255).astype(np.uint8); img[np.isnan(z)] = (236, 233, 226)
        Image.fromarray(img).save(f"{repo}/data/kamikura_{k}.jpg", quality=80, optimize=True, progressive=True)
        out[k] = {"label": spec["label"], "unit": spec["unit"], "ticks": spec["ticks"],
                  "stops": [[v, "#%02x%02x%02x" % c] for v, c in spec["stops"]]}
    return out


def _run_median(a, n):
    p = n // 2; ap = np.pad(np.asarray(a, float), p, mode="edge"); return np.array([np.nanmedian(ap[i:i + n]) for i in range(len(a))])


def _run_mean(a, n):
    p = n // 2; return np.convolve(np.pad(np.asarray(a, float), p, mode="edge"), np.ones(n) / n, mode="valid")


def _foot_xy():
    R = json.load(open("foot.json"))["profiles"]
    return (_run_mean(_run_median([r["foot_x"] for r in R], 5), 11), _run_mean(_run_median([r["foot_y"] for r in R], 5), 11))


def ground_data(z, x0, y1, frame):
    """Foot line and band, sample profiles, the audit, the alignment scores and the cadastre, for the page."""
    F = json.load(open("foot.json")); R = F["profiles"]; FS = F["summary"]
    fx = _run_mean(_run_median([r["foot_x"] for r in R], 5), 11); fy = _run_mean(_run_median([r["foot_y"] for r in R], 5), 11)
    lo, hi = [], []
    for r in R:
        v = np.array([r[k] for k in "ABCD"], float); v = v[np.abs(v - r["foot"]) <= 12]
        lo.append(v.min() if len(v) else r["foot"]); hi.append(v.max() if len(v) else r["foot"])
    lo, hi = _run_median(lo, 5), _run_median(hi, 5)
    left = [(r["fx"] + a * r["nx"], r["y"] + a * r["ny"]) for r, a in zip(R, lo)]
    right = [(r["fx"] + b * r["nx"], r["y"] + b * r["ny"]) for r, b in zip(R, hi)]
    band = Polygon(left + right[::-1]).buffer(0.5).buffer(-0.5)
    L = {"foot": path([list(zip(fx, fy))]), "foot_band": path(geoms_lines(band.simplify(0.3)), closed=True)}
    # four sample profiles inside the study area, 1 m steps, with the four definitions and the consensus
    zf = np.where(np.isnan(z), np.nanmedian(z), z)
    def zat(px, py): return ndi.map_coordinates(zf, [y1 - 0.5 - np.asarray(py), np.asarray(px) - x0 - 0.5], order=1)
    prof = []
    for yy in (-252240, -252300, -252370, -252440):
        r = min(R, key=lambda q: abs(q["y"] - yy)); sv = np.arange(-40, 61, 1.0)
        zv = zat(r["fx"] + sv * r["nx"], r["y"] + sv * r["ny"])
        prof.append({"y": round(r["y"], 1), "plain": round(r["plain"], 2), "s": sv.tolist(), "z": [round(float(v), 2) for v in zv],
                     **{k: round(r[k], 1) for k in "ABCD"}, "foot": round(r["foot"], 1), "step_deg": round(r["step_deg"], 1)})
    # the steepest 1 m step (step 6's statistic) in the 7 m window at the foot and in the same window 9–16 m up the face
    def maxstep(r, a, b):
        sp = np.arange(r["foot"] + a, r["foot"] + b + 0.01, 0.5)
        zz = zat(r["fx"] + sp * r["nx"], r["y"] + sp * r["ny"])
        return float(np.degrees(np.arctan(np.max(np.abs(zz[2:] - zz[:-2])))))
    st_foot = np.array([maxstep(r, -6, 1) for r in R]); st_face = np.array([maxstep(r, -16, -9) for r in R])
    foot = {"profiles": FS["profiles"], "length_m": round((len(R) - 1) * 2.0), "range_median_m": FS["range_median_m"],
            "range_p90_m": FS["range_p90_m"], "step_median": round(float(np.median(st_foot)), 1),
            "face_step_median": round(float(np.median(st_face)), 1), "face_step45_pct": round(100 * float(np.mean(st_face >= 45)), 1),
            "foot_steeper_pct": round(100 * float(np.mean(st_foot > st_face)), 1),
            "within5_pct": FS["within5_pct"], "dev": FS["dev_from_consensus_median_m"], "pair": FS["pair_median_abs_m"],
            "up_deg": FS["D_up_deg_median"], "dn_deg": FS["D_dn_deg_median"], "step45_pct": FS["step_over45_pct"],
            "step60_pct": round(100 * float(np.mean([r["step_deg"] >= 60 for r in R])), 1), "samples": prof}
    # the cadastre and what the test used
    P = json.load(open("parcels.json"))
    rings = lambda kinds: [p["rings"][0] for p in P["parcels"] if p["kind"] in kinds and p["rings"]]
    L["parcels"] = path(rings(("private", "other")), closed=True)
    L["lwater"] = path(rings(("water",)), closed=True)
    L["lroad"] = path(rings(("road", "strip")), closed=True)
    B = json.load(open("backs.json"))
    L["backs"] = path(B["backs"])
    W = json.load(open("walls.json"))
    L["walls"] = path([w["line"] for w in W])
    A = json.load(open("align.json"))
    scores = {}
    for k, v in A["classes"].items():
        b = next((b for b in v["bands"] if b["from"] == (-15 if k == "walls" else 0)), None)
        scores[k] = {"band": [b["from"], b["to"]] if b else None, "follow": b.get("follow_foot_pct") if b else None,
                     "chance": b.get("chance_pct") if b else None, "p": b.get("p") if b else None, "p_100": b.get("p_100") if b else None,
                     "n": b.get("n_disc") if b else 0, "units": b.get("n_units") if b else 0, "units_follow": b.get("n_units_follow") if b else 0,
                     "robust": v.get("robust"),
                     "beyond": [{kk: bb.get(kk) for kk in ("from", "to", "follow_foot_pct", "chance_pct", "p", "p_100", "n_disc", "n_units", "n_units_follow", "robust")}
                                for bb in v["bands"] if bb["from"] >= 25]}
    audit = json.load(open("terrain_audit.json"))
    ex = [(round(b["follow_foot_pct"] - b["chance_pct"], 1), k, b["from"], b["to"], b["p"], b["robust"]["significant"]) for k, v in scores.items()
          for b in v["beyond"] if b.get("follow_foot_pct") is not None]
    beyond = max(ex)
    # beyond 25 m: every band significant in at least 3 of the six runs (either shift), with how many lines carry it
    beyond_hits = [{"class": k, "band": [b["from"], b["to"]], "significant": b["robust"]["significant"],
                    "significant_100": b["robust"]["significant_100"], "significant_both": b["robust"]["significant_both"],
                    "n": b["n_disc"], "units": b["n_units"], "units_follow": b["n_units_follow"]}
                   for k, v in scores.items() for b in v["beyond"] if b.get("robust") and max(b["robust"]["significant"], b["robust"]["significant_100"]) >= 3]
    others = [max(b["robust"]["significant"], b["robust"]["significant_100"]) for k, v in scores.items() for b in v["beyond"]
              if b.get("robust") and max(b["robust"]["significant"], b["robust"]["significant_100"]) < 3]
    runs_west = [A["offsets"]["cadastre_west"]["median_m"]] + [r["cadastre_west"] for r in A["sensitivity"]["_offsets"]]
    weak = ("fronts", "temple", "walls", "legal_water")     # the classes that show nothing within 25 m
    out = {"foot": foot, "scores": scores, "beyond_max": {"excess": beyond[0], "class": beyond[1], "band": [beyond[2], beyond[3]], "p": beyond[4], "significant_runs": beyond[5]},
           "beyond_hits": beyond_hits, "beyond_rest_max_sig": max(others),
           "walls_town_m": sum(b["length_m"] for b in A["classes"]["walls"]["bands"] if b["from"] >= 0),
           "weak_max_sig": max(max(scores[k]["robust"]["significant"], scores[k]["robust"]["significant_100"]) for k in weak if scores[k].get("robust")),
           "cad_west_range": [min(runs_west), max(runs_west)], "offsets": A["offsets"], "wiggle": A["wiggle"], "lvc": A["legal_vs_channel"],
           "grid": {"town": A["grid_deg"], "R": A["grid_R"], "front_near": A["near_front_deg"], "front_regional": A["regional_front_deg"]},
           "walls": A["walls"], "temple_parcels": A["temple_parcels"], "sens_offsets": A["sensitivity"]["_offsets"],
           "courses": A["courses"], "courses_sim": A["courses_sim"],
           "audit": {"coverage": audit["coverage"], "dem5": audit["dem5_vs_1"], "buildings": audit["buildings"],
                     "control": [c for c in audit["control"] if c["kind"] != "spot height (1:25,000)"], "sigma_lrm": audit["sigma_lrm_m"],
                     "sigma_curv": audit["sigma_curv_m"]},
           "cadastre": {k: P[k] for k in ("sheet", "name", "crs", "n_parcels")} | {"aff": {k: v for k, v in P["aff"].items() if k != "params"}
                        | {"area_factor": round(abs(P["aff"]["params"][0] * P["aff"]["params"][3] - P["aff"]["params"][1] * P["aff"]["params"][2]), 3)},
                        "sim": {k: v for k, v in P["sim"].items() if k != "params"}, "anchor": P["anchor"],
                        "kinds": {("numbered" if k == "private" else k): sum(1 for p in P["parcels"] if p["kind"] == k) for k in ("private", "road", "water", "strip", "other")}}}
    return L, out


def contours(z, x0, y1, levels, clip, min_len=14, tol=0.35):
    zs = ndi.gaussian_filter(np.where(np.isnan(z), np.nanmin(z), z), 1.4)
    res = {}
    for lv in levels:
        ls = []
        for c in measure.find_contours(zs, lv):
            line = LineString([(x0 + 0.5 + col, y1 - 0.5 - row) for row, col in c])
            if line.length < min_len: continue
            line = line.simplify(tol).intersection(clip)
            ls += [l for l in geoms_lines(line) if LineString(l).length >= min_len]
        res[lv] = ls
    return res


def main():
    repo = sys.argv[1]
    st = json.load(open("study.json")); tj = json.load(open("terrain.json")); tz = np.load("terrain.npz")
    z = tz["z"]; x0, y1, W, H = [float(v) for v in tz["frame"]]
    osm_l = json.load(open("osm.json"))["elements"]
    osm = {e["id"]: e for e in osm_l if e["type"] == "way" and e.get("geometry")}
    nodes = {e["id"]: e for e in osm_l if e["type"] == "node"}
    frame = box(x0, y1 - H, x0 + W, y1)
    os.makedirs(f"{repo}/data", exist_ok=True)

    relief(z, f"{repo}/data/kamikura_relief.jpg")
    img = {"href": "data/kamikura_relief.jpg", "x": round(pg(x0, y1)[0], 4), "y": round(pg(x0, y1)[1], 4), "w": W / 100, "h": H / 100}
    tp = np.load("terrain_plus.npz")
    bases = ground_images(z, tp, repo)
    for k in bases: bases[k]["href"] = f"data/kamikura_{k}.jpg"

    poly = Polygon(st["poly"][0])
    near = poly.buffer(260).intersection(frame)               # fine contours only around the study area
    cs1 = contours(z, x0, y1, [float(v) for v in range(3, 15)], near)
    cs5 = contours(z, x0, y1, [float(v) for v in range(15, 255, 5)], frame, min_len=20, tol=0.6)
    L = {}
    L["c1"] = path([l for v in cs1.values() for l in v])
    L["c5"] = path([l for v, ls in cs5.items() if v % 25 for l in ls])
    L["c25"] = path([l for v, ls in cs5.items() if v % 25 == 0 for l in ls])
    lab = []
    for v, ls in cs5.items():                                 # height labels on the 25 m contours, mid-line
        if v % 25 or not ls: continue
        lng = max(ls, key=lambda l: LineString(l).length)
        if LineString(lng).length < 120: continue
        p = LineString(lng).interpolate(0.5, normalized=True); a = LineString(lng).interpolate(0.52, normalized=True)
        ang = math.degrees(math.atan2(-(a.y - p.y), a.x - p.x))
        if ang > 90: ang -= 180
        if ang < -90: ang += 180
        lab.append([*map(lambda q: round(q, 4), pg(p.x, p.y)), f"{int(v)} m", round(ang, 1)])

    GL, ground = ground_data(z, x0, y1, frame)
    L.update(GL)
    L["poly"] = path(st["poly"], closed=True)
    L["break"] = path([l for l in geoms_lines(unary_union([LineString(q) for q in tj["break"]]).intersection(near))])
    def way(w): return LineString([LL2P.transform(p["lon"], p["lat"]) for p in osm[w]["geometry"]])
    # water: GSI's drawn water areas (the channel between its banks) and single-line streams; the last stretch of the
    # Kamikura-yama stream, which GSI stops at the slope foot, from OSM
    wa = unary_union([Polygon(r[0]) for r in st["water_area"]]).intersection(frame)
    L["water_area"] = path(geoms_lines(wa.simplify(0.15)), closed=True)
    L["water"] = path([l for l in st["water_lines"]] + geoms_lines(way(499568828).intersection(frame)))
    roads, paths, steps, r42 = [], [], [], []
    for e in osm.values():
        t = e.get("tags", {}); h = t.get("highway")
        if not h or h in ("traffic_signals",): continue
        g = way(e["id"]).intersection(frame)
        if g.is_empty: continue
        if t.get("name") == "国道42号" or h in ("trunk", "primary", "secondary"): r42.append(g)
        elif h == "steps": steps.append(g)
        elif h in ("path", "footway", "track", "pedestrian"): paths.append(g)
        else: roads.append(g)
    L["roads"] = path([l for g in roads for l in geoms_lines(g)])
    L["major"] = path([l for g in r42 for l in geoms_lines(g)])
    L["paths"] = path([l for g in paths for l in geoms_lines(g)])
    L["steps"] = path([l for g in steps for l in geoms_lines(g)])
    school = Polygon([LL2P.transform(p["lon"], p["lat"]) for p in osm[1333972521]["geometry"]])
    L["school"] = path([list(school.exterior.coords)], closed=True)
    # the religious flow (sacred.py): the shrine's lower precinct alone (OSM way 500803106) and, beside it, the grounds
    # of the 出雲大社新宮教会 (way 500803107, formerly drawn as part of the precinct), the ritual route, the small shrines
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sacred
    SL, ground["sacred"] = sacred.build(z, x0, y1, frame, st, pg, path)
    L.update(SL)
    # buildings coloured by the step-8 test: the consensus foot, the town grid of GSI road edges, the same rule
    import importlib.util
    spec = importlib.util.spec_from_file_location("a8", os.path.join(os.path.dirname(os.path.abspath(__file__)), "08_align.py"))
    a8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(a8)
    foot = a8.Foot(json.load(open("foot.json"))); grid = json.load(open("align.json"))["grid_deg"]
    by = {"foot": [], "grid": [], "both": [], "far": []}
    for b in st["bld"]:
        P = Polygon(b["ring"])
        if not frame.intersects(P): continue
        r = np.asarray(P.minimum_rotated_rectangle.exterior.coords); e1, e2 = r[1] - r[0], r[2] - r[1]
        e = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2; th = a8.bearing(e[0], e[1])
        d, fd, inside = foot.at([(P.centroid.x, P.centroid.y)])
        if not inside[0] or d[0] > 400 or d[0] < -15: c = "far"
        elif a8.adiff(fd[0], grid) < 10: c = "both"
        else: c = "foot" if a8.adiff(th, fd[0]) < a8.adiff(th, grid) else "grid"
        by[c].append(b["ring"])
    for k, v in by.items(): L["b_" + k] = path(v, closed=True)
    L["b_in"] = path([b["ring"] for b in st["bld"] if b["in"]], closed=True)
    L["b_robust"] = path([b["ring"] for b in st["bld"] if b["code"] in (3102, 3103, 3112)], closed=True)

    def feats(fn, filt=lambda p: True):
        for ft in json.load(open(fn, encoding="utf-8"))["features"]:
            if ft.get("geometry") and filt(ft["properties"]):
                g = shape(ft["geometry"])
                if g.intersects(box(135.97, 33.71, 136.0, 33.735)): yield g.buffer(0)
    FL = proj(unary_union([g for fn in ("8606010001", "8606010002", "8606010006") for g in feats(f"{KSJ}/20_想定最大規模/A31a-20-25_86_{fn}_10.geojson")])).intersection(frame)
    a33 = f"{KSJ}/A33-25_30Polygon.geojson"
    RED = proj(unary_union(list(feats(a33, lambda p: p["A33_002"] in (2, 4))))).intersection(frame)
    YEL = proj(unary_union(list(feats(a33, lambda p: p["A33_002"] not in (2, 4))))).intersection(frame).difference(RED)
    TS = proj(unary_union(list(feats(f"{KSJ}/A40-16_30_GML/A40-16_30.geojson")))).intersection(frame)
    rit = f"{KSJ}/A55-24_30207_GEOJSON/30207_ritteki.geojson"
    RIZ = proj(unary_union(list(feats(rit, lambda p: p["AreaType"] == "居住誘導区域")))).intersection(frame)
    for k, g in (("flood", FL), ("ls_red", RED), ("ls_yellow", YEL), ("tsunami", TS)):
        L[k] = path(geoms_lines(g.simplify(0.8)), closed=True)
    L["riz"] = path(geoms_lines(RIZ.boundary.intersection(frame).simplify(0.8)))
    # does the residential-inducement area reach onto the slope? every 1 m cell of the study area, against the foot
    gx, gy = np.meshgrid(x0 + 0.5 + np.arange(int(W)), y1 - 0.5 - np.arange(int(H)))
    cin = contains_xy(poly, gx, gy); cx_, cy_ = gx[cin], gy[cin]
    d_, _, ok_ = foot.at(np.column_stack([cx_, cy_])); inr = contains_xy(RIZ, cx_, cy_)
    ground["riz"] = {"cells_upslope": int((inr & (d_ < 0)).sum()), "cells_upslope_total": int((d_ < 0).sum()),
                     "min_below_foot_m": round(float(d_[inr].min()), 1) if inr.any() else None}
    wg = ground["wiggle"]["channel"]; yb = poly.bounds
    wg["in_study_m"] = round(max(0.0, min(wg["y_from"], yb[3]) - max(wg["y_to"], yb[1])), 1)
    wg["amp_ratio"] = round(wg["line_wiggle_sd_m"] / wg["foot_wiggle_sd_m"], 2)        # the channel's bends against the foot's
    # the break-of-slope rule's plain (whole frame), as distinct from the study area's plain (stats.z_plain_med)
    ground["plain_frame_m"] = tj["plain_m"]
    # what the channel-course reading covers: the drawing's extent, against the study area
    PJ = json.load(open("parcels.json"))["parcels"]
    cover = unary_union([Polygon(q["rings"][0]).buffer(0) for q in PJ if q["rings"]])
    chn = LineString(st["ichida"]); cin = chn.intersection(poly)
    P4 = a8.pieces(chn.intersection(cover.buffer(2)), 4.0)
    out_ = [q for q in P4 if not poly.contains(Point(q[0], q[1]))]
    ground["courses_extent"] = {"total_m": round(sum(q[3] for q in P4)), "outside_study_m": round(sum(q[3] for q in out_)),
                                "outside_north": all(q[1] > yb[3] - 30 for q in out_),
                                "uncovered_in_study_m": round(cin.difference(cover.buffer(2)).length)}
    # the strip between the foot and the drawn waterway: how many numbered parcels span it, row by row
    lwr = json.load(open("offsets.json"))["legal_water"]
    num = [Polygon(q["rings"][0]).buffer(0) for q in PJ if q["kind"] == "private" and q["rings"]]
    spans, fill = [], []
    for yy, off in lwr:
        fx = float(np.interp(yy, foot.yy[::-1], foot.x[::-1])); seg = LineString([(fx, yy), (fx + off, yy)])
        hits = [g.intersection(seg).length for g in num if g.intersects(seg)]; hits = [h for h in hits if h >= 2.0]
        spans.append(len(hits)); fill.append(sum(hits) / max(off, 1e-6))
    ground["lots_between"] = {"rows": len(spans), "one_parcel_pct": round(100 * float(np.mean(np.array(spans) == 1)), 1),
                              "none_pct": round(100 * float(np.mean(np.array(spans) == 0)), 1),
                              "filled_median_pct": round(100 * float(np.median(fill)), 1)}
    tr = LineString(st["transect"])
    L["transect"] = path([list(tr.coords)])

    def nd(i): return LL2P.transform(nodes[i]["lon"], nodes[i]["lat"])
    def ll(lon, lat): return LL2P.transform(lon, lat)
    # [key, text, x, y (page), anchor, dx, dy, class, systems]
    ich = LineString(st["ichida"]); ich_lab = ich.interpolate(ich.project(Point(*ll(135.98520, 33.72610))))
    raw = [   # every place here has an independent reference in kansai/qa/points.toml (kmk_*)
        ["summit", "神倉神社 · Gotobiki-iwa", nd(2270139651), "start", 8, -6, "em", "bichikei keidai shinko"],
        ["steps", "538 stone steps", ll(135.98330, 33.72366), "end", -6, -4, "", "michi keidai bichikei shinko"],
        ["entrance", "entrance · 下馬 stone", nd(4908399279), "start", 8, 16, "", "keidai michi shinko"],
        ["manzan", "満山社", nd(4908398790), "end", -7, 4, "small only", "shinko"],
        ["naka_jizo", "中ノ地蔵堂", nd(4908399232), "end", -7, 4, "small only", "shinko"],
        ["iwatate", "天磐盾 stele", nd(4908399260), "end", -7, 12, "small only", "shinko"],
        ["sarutahiko", "猿田彦神社・神倉三宝荒神社", nd(4908399267), "end", -7, -4, "small only", "shinko"],
        ["izumo", "出雲大社新宮教会", ll(135.984343, 33.724104), "start", 8, 12, "small only", "shinko"],
        ["horibata", "神倉堀端都市下水路", (ich_lab.x, ich_lab.y), "start", 7, 4, "water", "suikei"],
        ["mstream", "Kamikura-yama stream", ll(135.98330, 33.72446), "end", -4, -6, "water small", "suikei"],
        ["school", "神倉小学校 Kamikura Elementary", ll(135.98503, 33.72506), "middle", 0, 4, "", "kokyo"],
        ["myoshin", "妙心寺", ll(135.984329, 33.724781), "end", -7, 2, "small", "keidai seikatsu shinko"],
        ["engawa", "Youth Library えんがわ", ll(135.984299, 33.724689), "end", -7, 12, "small", "kokyo seikatsu"],
        ["oishii", "おいしいパーク", ll(135.98417, 33.72512), "end", -7, 4, "small", "kokyo seikatsu"],
        ["soo", "宗応寺", ll(135.984268, 33.725773), "end", -7, 4, "small", "keidai shinko"],
        ["gym", "gym · shelter", ll(135.98524, 33.72488), "start", 7, 4, "small only", "saigai"],
        ["schoolhouse", "school building · tsunami refuge", ll(135.98517, 33.72553), "start", 7, -4, "small only", "saigai"],
        ["r42", "国道42号", ll(135.98657, 33.72600), "start", 6, 0, "small", "michi"],
        ["cityhall", "新宮市役所 city hall", nd(1423067948), "end", -8, -8, "em", "michi"],
        ["chiho", "千穂ヶ峰 ↑", ll(135.98150, 33.72660), "middle", 0, 0, "small", "bichikei"],
    ]
    pts = [[k, t, *map(lambda q: round(q, 4), pg(*xy)), a, dx, dy, c, s] for k, t, xy, a, dx, dy, c, s in raw]

    # the rule of each edge, written just outside the middle of that edge
    ring = LineString(list(poly.exterior.coords))
    offl = unary_union([LineString(q) for q in tj["offset"]])
    edge_geo = {"west": ring.intersection(offl.buffer(0.6)), "north": ring.intersection(LineString(st["edges"]["north"]).buffer(0.6)),
                "east": ring.intersection(LineString(st["edges"]["east"]).buffer(0.6)), "south": ring.intersection(LineString(st["edges"]["south"]).buffer(0.6))}
    edge_txt = {"west": "slope break + 25 m", "north": "first full block", "east": "school compound edge", "south": "entrance street"}
    cen = poly.centroid
    elab = []
    for k, g in edge_geo.items():
        parts = [p for p in getattr(g, "geoms", [g]) if not p.is_empty and p.geom_type in ("LineString", "Polygon")]
        if not parts: raise SystemExit(f"edge {k} not found on the polygon")
        longest = max(parts, key=lambda p: p.length)
        m = longest.boundary.centroid if longest.geom_type == "Polygon" else longest.interpolate(0.5, normalized=True)
        dx, dy = m.x - cen.x, m.y - cen.y; nrm = math.hypot(dx, dy) or 1.0          # outward, in page axes (y down)
        elab.append([*map(lambda q: round(q, 4), pg(m.x, m.y)), edge_txt[k], k, [round(dx / nrm, 3), round(-dy / nrm, 3)]])

    hx0, hy0, hx1, hy1 = poly.buffer(70).bounds
    home = [*pg(hx0, hy1), *pg(hx1, hy0)]
    tr_b = tr.buffer(40).bounds
    data = {"img": img, "layers": L, "pts": pts, "clab": lab, "home": [round(v, 4) for v in home],
            "frame": [round(v, 4) for v in (*pg(x0, y1), *pg(x0 + W, y1 - H))],
            "transect": [[round(v, 4) for v in pg(*p)] for p in st["transect"]], "tsplit": st["transect_split_m"],
            "tcum": [round(LineString(st["transect"][:i + 1]).length, 1) if i else 0.0 for i in range(len(st["transect"]))],
            "trbox": [round(v, 4) for v in (*pg(tr_b[0], tr_b[3]), *pg(tr_b[2], tr_b[1]))],
            "profile": st["profile"], "runs": sacred.relabel_runs(st["profile_runs"], st), "stats": {k: v for k, v in st["stats"].items() if k not in ("riz_in_mountain_pct", "precinct_m2")},   # see ground.sacred.grounds
            "edges": elab, "bases": bases, "ground": ground}
    js = "window.__KMK=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(f"{repo}/data/kamikura.js", "w", encoding="utf-8").write(js)

    # ------------------------------------------------------------ GIS downloads (WGS84)
    def tll(g): return transform(lambda x, y, z=None: P2LL.transform(x, y), g)
    def r7(geom):
        def rnd(c):
            return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 7), round(c[1], 7)]
        g = mapping(geom); g = {"type": g["type"], "coordinates": rnd(g["coordinates"])}; return g
    s = st["stats"]
    feats_out = [
        {"type": "Feature", "properties": {"name": "神倉山麓 study area · Kamikura mountain foot", "area_ha": s["area_ha"],
                                           "ns_m": s["ns_m"], "ew_m": s["ew_m"], "buildings": s["bld_n"]}, "geometry": r7(tll(poly))},
        {"type": "Feature", "properties": {"name": "west edge", "rule": "25 m (horizontal) upslope of the slope break on GSI DEM1A (1 m)"},
         "geometry": r7(tll(poly.exterior.intersection(unary_union([LineString(q) for q in tj["offset"]]).buffer(0.5))))},
        {"type": "Feature", "properties": {"name": "north edge", "rule": "lane closing the first full block north of the school and the temple row (OSM 266991552, 121369902)"},
         "geometry": r7(tll(LineString(st["edges"]["north"]).intersection(poly.buffer(0.5))))},
        {"type": "Feature", "properties": {"name": "east edge", "rule": "street bounding the compound of 神倉小学校 (OSM: 千穂小学校) on the east, continued south (OSM 121367848, 1031510641, 121367953)"},
         "geometry": r7(tll(LineString(st["edges"]["east"]).intersection(poly.buffer(0.5))))},
        {"type": "Feature", "properties": {"name": "south edge", "rule": "street just south of the shrine-entrance cluster, carried west across the foot of the steps (OSM 121367975, 121370515, 499568826)"},
         "geometry": r7(tll(LineString(st["edges"]["south"]).intersection(poly.buffer(0.5))))},
        {"type": "Feature", "properties": {"name": "slope break", "rule": "edge of ground ≥1 m above the plain and steeper than 12° (or ≥3 m above it), connected to the slopes above 40 m; GSI DEM1A"},
         "geometry": r7(tll(unary_union([LineString(q) for q in tj["break"]]).intersection(near)))},
        {"type": "Feature", "properties": {"name": "mountain foot (consensus)", "rule": "per-profile median of four definitions (mask edge, plain + 1 m, greatest concavity, two-segment hinge) on cross-profiles every 2 m; GSI DEM1A"},
         "geometry": r7(tll(LineString(list(zip(*_foot_xy())))))},
        {"type": "Feature", "properties": {"name": "transect", "from": "神倉神社 (summit, at Gotobiki-iwa)", "via": "the path and the stone steps (OSM 121369321, 121366071) to the bridge over 市田川",
                                           "to": "新宮市役所", "length_m": s["transect_m"]}, "geometry": r7(tll(tr))},
    ]
    gj = {"type": "FeatureCollection", "name": "kamikura_study", "crs_note": "WGS84 lon/lat; built in JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674)",
          "source": "no-one-is-an-island · Kansai page · kansai/tools/kamikura (GSI DEM1A, © OpenStreetMap contributors ODbL)", "features": feats_out}
    json.dump(gj, open(f"{repo}/data/kamikura_study.geojson", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def kml_coords(g):
        if g.geom_type == "LineString": return [" ".join(f"{x},{y},0" for x, y in g.coords)]
        if g.geom_type == "MultiLineString": return [" ".join(f"{x},{y},0" for x, y in l.coords) for l in g.geoms]
        return []
    pm = []
    for f in feats_out:
        g = shape(f["geometry"]); nm = f["properties"]["name"]
        desc = "; ".join(f"{k}: {v}" for k, v in f["properties"].items() if k != "name")
        if g.geom_type == "Polygon":
            ring = " ".join(f"{x},{y},0" for x, y in g.exterior.coords)
            pm.append(f"<Placemark><name>{nm}</name><description>{desc}</description><styleUrl>#area</styleUrl><Polygon><outerBoundaryIs><LinearRing><coordinates>{ring}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
        else:
            for c in kml_coords(g):
                pm.append(f"<Placemark><name>{nm}</name><description>{desc}</description><styleUrl>#{'tr' if nm == 'transect' else 'edge'}</styleUrl><LineString><coordinates>{c}</coordinates></LineString></Placemark>")
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Kamikura mountain foot · study area</name>'
           '<Style id="area"><LineStyle><color>ff2f5fd3</color><width>3</width></LineStyle><PolyStyle><color>332f5fd3</color></PolyStyle></Style>'
           '<Style id="edge"><LineStyle><color>ff2f5fd3</color><width>2</width></LineStyle></Style>'
           '<Style id="tr"><LineStyle><color>ff944f2f</color><width>3</width></LineStyle></Style>' + "".join(pm) + "</Document></kml>\n")
    open(f"{repo}/data/kamikura_study.kml", "w", encoding="utf-8").write(kml)
    # the registered cadastre (approximate; no parcel numbers)
    P = json.load(open("parcels.json"))
    cad = {"type": "FeatureCollection", "name": "kamikura_cadastre",
           "source": "「登記所備付地図データ 新宮市」（法務省） https://www.geospatial.jp/ckan/dataset/houmusyouchizu-2026-1-1430 を加工して作成 "
                     "(sheet 30207-1704-59, arbitrary coordinates, registered to GSI road edges by an affine transform; "
                     f"road-parcel fit median {P['aff']['road_median_m']} m) — no-one-is-an-island, kansai/tools/kamikura",
           # kind: numbered (a lot with a 地番: the drawing records lots, not owners), road (道), water (水), strip (長狭物)
           "features": [{"type": "Feature", "properties": {"kind": "numbered" if p["kind"] == "private" else p["kind"]}, "geometry": r7(tll(Polygon(p["rings"][0])))}
                        for p in P["parcels"] if p["rings"] and len(p["rings"][0]) > 3]}
    json.dump(cad, open(f"{repo}/data/kamikura_cadastre.geojson", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    sz = {f: os.path.getsize(f"{repo}/data/{f}") for f in ("kamikura.js", "kamikura_relief.jpg", "kamikura_elev.jpg", "kamikura_slope.jpg",
                                                         "kamikura_lrm.jpg", "kamikura_curv.jpg", "kamikura_study.geojson", "kamikura_study.kml",
                                                         "kamikura_cadastre.geojson")}
    print(sz, {k: len(v) for k, v in L.items()})


if __name__ == "__main__":
    main()
