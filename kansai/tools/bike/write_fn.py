import json, os, sys, math
from pagegeo import pg
H = os.getcwd()
R = json.load(open(os.path.join(H, "fn_region.json"))); T = json.load(open(os.path.join(H, "fn_town.json"))); M = json.load(open(os.path.join(H, "fn_misc.json")))
# frames (page units)
x0, y0 = pg(135.976, 33.734); x1, y1 = pg(136.001, 33.716)
town_frame = [round(min(x0, x1), 2), round(min(y0, y1), 2), round(max(x0, x1), 2), round(max(y0, y1), 2)]
xs = [n["x"] for n in R["nodes"]]; ys = [n["y"] for n in R["nodes"]]
reg_frame = [round(min(xs) - 25, 1), round(min(ys) - 25, 1), round(max(xs) + 25, 1), round(max(ys) + 25, 1)]
# building dots: integer metres from the town frame's corner + three classes (directness bins; 0 = no access within 60 m)
BINS = [1.25, 1.35, 1.45, 1.55, 1.7, 1.9]          # class k = number of bins below, +1
def cls(v):
    if v is None or v == 0: return 0
    if v < 0: return 9
    d = v / 100.0; return 1 + sum(1 for b in BINS if d > b)
dots = []
for x, y, w, b, c in T["dots"]:
    dots += [int(round((x - town_frame[0]) * 100)), int(round((y - town_frame[1]) * 100)), cls(w) * 100 + cls(b) * 10 + cls(c)]
out = {"frames": {"town": town_frame, "region": reg_frame}, "bins": BINS,
       "region": {"chains": R["chains"], "nodes": R["nodes"], "options": R["options"], "closures": [c for c in M["closures"] if c["chains"]], "mw": M["mw"], "mw_names": M["mw_names"]},
       "town": {"nets": T["nets"], "dots": dots, "legs": T["legs"], "photos": M["photos"], "water": json.load(open(os.path.join(H, "fn_twater.json")))["water"]}}
# ---- every number the text quotes, recomputed here (checked by kansai/qa/run.py, "fn" claims) ----
import statistics as st
man = [x for x in json.load(open(os.path.join(H, "..", "photos", "manifest.json"))) if not x.get("track") and x.get("lat")]
legs = T["legs"]
def share(rows, f): return round(100 * sum(1 for r in rows if f(r)) / len(rows))
L1, L2 = legs[0]["rows"], legs[1]["rows"]
V = json.load(open(os.path.join(H, "validate_final.json")))
Tw = json.load(open(os.path.join(H, "town", "town_out.json")))
def med(m): v = [x for x in Tw["dir"][m] if x is not None and x > 0]; return round(st.median(v), 2)
nocar = Tw["noacc"]["car"]
ch = R["chains"]; O = R["options"]
from shapely.geometry import LineString, shape
from shapely.ops import unary_union, transform as _tf
from pyproj import Transformer as _T
_tr = _T.from_crs(4326, 6674, always_xy=True).transform
_K = json.load(open(os.path.join(os.getcwd(), "..", "geo", "kmk", "gsi_water.geojson")))
_CH = _tf(_tr, unary_union([shape(f["geometry"]) for f in _K["features"]]))
leg2_channel_m = round(LineString(Tw["legs"][1]["xy"]).intersection(_CH.buffer(25)).length)
stats = {
  "ride": {"photos_gps": len(man), "photos_shown": len(M["photos"]), "hpe_min": round(min(x["hpe_m"] for x in man), 1), "hpe_max": round(max(x["hpe_m"] for x in man), 1),
           "t_first": min(x["time"] for x in man)[11:16], "t_last": max(x["time"] for x in man)[11:16],
           "leg1_km": round(legs[0]["len"] / 1000, 1), "leg2_km": round(legs[1]["len"] / 1000, 1), "leg1_m": legs[0]["len"], "leg2_m": legs[1]["len"],
           "leg1_wide_pct": share(L1, lambda r: r[1] in ("5.5m-13m未満", "13m-19.5m未満", "19.5m以上")), "leg1_shops_pct": share(L1, lambda r: r[4] > 0),
           "leg2_narrow_pct": share(L2, lambda r: r[1] == "3m未満"), "leg2_water_pct": share(L2, lambda r: r[6]), "leg2_sacred_pct": share(L2, lambda r: r[5]), "leg2_channel_m": leg2_channel_m},
  "town": {"bld_n": len(Tw["B"]), "dest_n": 260, "med_walk": med("walk"), "med_bike": med("bike"), "med_car": med("car"),
           "nocar_n": nocar, "nocar_pct": round(100 * nocar / len(Tw["B"]))},
  "region": {"corr_km": round(sum(c["len"] for c in ch) / 1000), "chains_n": len(ch),
             "hh_km": round(O["hongu-hayatama"]["list"][0]["len"] / 1000, 1), "hh_up": O["hongu-hayatama"]["list"][0]["up"],
             "hn_km": round(O["hayatama-nachi"]["list"][0]["len"] / 1000, 1), "hn_up": O["hayatama-nachi"]["list"][0]["up"],
             "nh_km": round(O["nachi-hongu"]["list"][0]["len"] / 1000, 1), "nh_up": O["nachi-hongu"]["list"][0]["up"],
             "hn_pcr_km": round(O["hayatama-nachi"]["list"][0]["pcr"] / 1000, 1),
             "rain": {c["no"]: dict({"mm": c["mm"], "km": round(c["len"] / 1000, 1)}, **({"hr": c["hr"]} if c.get("hr") else {})) for c in M["closures"] if c["chains"]}},
  "dem": V}
# the compass correction applied to the photographs (export_misc.py): World Magnetic Model 2025 at each photograph
from pygeomag import GeoMag
_W = GeoMag(coefficients_file="wmm/WMM_2025.COF")
_dec = [_W.calculate(glat=x["lat"], glon=x["lon"], alt=0, time=2025 + (270.5 / 365)).d for x in man]   # 28 Sep 2025 = day 271
stats["ride"]["decl_w"] = round(-sum(_dec) / len(_dec), 1)
# rain: per route between Hongū and Hayatama, the lowest threshold among the sections it follows for 200 m or more
def rain_of(O):
    on = {c for c, o in O["seq"]}; mm = None
    for cl in out["region"]["closures"]:
        if any(int(k) in on and v >= 200 for k, v in cl["chains"].items()): mm = cl["mm"] if mm is None else min(mm, cl["mm"])
    return mm
HH = O["hongu-hayatama"]["list"]; rr = [rain_of(o) for o in HH]
top = max(r for r in rr if r is not None)
stats["region"]["hh_n"] = len(HH); stats["region"]["hh_closing"] = sum(1 for r in rr if r is not None)
stats["region"]["hh_longest"] = " and ".join(chr(65 + i) for i, r in enumerate(rr) if r == top); stats["region"]["hh_longest_mm"] = top
stats["region"]["hh_longest_up_min"] = min(o["up"] for o, r in zip(HH, rr) if r == top)
# the one grade the table withholds (the mapped line on 県道45 below 高瀬峠, OSM surface=ground): steepest 200 m
stats["region"]["unverified_grade"] = round(max(o["gmax"] for pr in O.values() for o in pr["list"] if o["gmax"] > 25))
# where the steepest 200 m lies: within 400 m of either end of the route (a shrine's approach) or on the way
CH = {c["id"]: c for c in R["chains"]}
def steep_at_end(o):
    pts = []; cum = 0
    for cid, d in o["seq"]:
        c = CH[cid]; h = c["h"] if d > 0 else c["h"][::-1]; st = c["len"] / (len(h) - 1)
        pts += [(cum + k * st, h[k]) for k in range(len(h))]; cum += c["len"]
    best = (0, 0, 0); j = 0
    for a in range(len(pts)):
        while j < len(pts) and pts[j][0] - pts[a][0] < 200: j += 1
        if j >= len(pts): break
        g = abs(pts[j][1] - pts[a][1]) / (pts[j][0] - pts[a][0])
        if g > best[0]: best = (g, pts[a][0], pts[j][0])
    return best[1] < 400 or cum - best[2] < 400
allo = [o for pr in O.values() for o in pr["list"]]
stats["region"]["routes_n"] = len(allo); stats["region"]["steep_at_shrine"] = sum(1 for o in allo if steep_at_end(o))
# leg 1 on the station road (新宮停車場線): the leg's line inside 4 m of the OSM ways of that name
_st = unary_union([_tf(_tr, LineString([(q["lon"], q["lat"]) for q in e["geometry"]])) for e in json.load(open(os.path.join(H, "roads.json")))["elements"]
                   if e["type"] == "way" and e.get("tags", {}).get("name") == "新宮停車場線"])
stats["ride"]["leg1_station_m"] = int(round(LineString(Tw["legs"][0]["xy"]).intersection(_st.buffer(4)).length, -1))
# the Mie sections given by place names only: drawn length between the places, against Mie's own length
stats["region"]["mie_between"] = {c["no"]: {"drawn_km": round(c["len"] / 1000, 1), "mie_km": c["km_official"]} for c in out["region"]["closures"] if c.get("between_places")}
out["stats"] = stats
# town place names: positions are the independent references in kansai/qa/points.toml (fn_* = kmc_* / station)
TLAB = [("fn_asuka", "阿須賀神社", "Asuka-jinja", 135.997292, 33.728475), ("fn_hayatama", "熊野速玉大社", "Hayatama Taisha", 135.983542, 33.732175),
        ("fn_kamikura", "神倉神社の石段の下", "foot of the Kamikura steps", 135.984192, 33.724297), ("fn_station", "新宮駅", "Shingū station", 135.99408, 33.72508)]
out["town"]["labels"] = [{"key": k, "ja": ja, "en": en, "x": round(pg(lo, la)[0], 3), "y": round(pg(lo, la)[1], 3)} for k, ja, en, lo, la in TLAB]
print(json.dumps(stats, ensure_ascii=False), file=sys.stderr)
s = "window.__FN=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(os.path.join(sys.argv[1], "data", "fieldnotes.js"), "w", encoding="utf-8").write(s)
print("fieldnotes.js", len(s.encode()) // 1024, "KB; dots", len(dots) // 3, file=sys.stderr)
