"""Write kansai/data/risk.js (window.__RISK): what the page draws and every number its text quotes about evacuation
margins, tiered exposure, the plan's zones and the road network. The QA gate (kansai/qa/run.py, "rk" claims) reads the
numbers back from this file.
usage: export.py <kansai directory>"""
import json, os, sys, numpy as np
from shapely.geometry import shape, mapping
from shapely.ops import transform as tfm
import cfg, hz
sys.path.insert(0, cfg.BIKE)
from pagegeo import pgm, d_of
K = sys.argv[1]
B = np.load("bld.npz", allow_pickle=True); E = np.load("evac.npz", allow_pickle=True)
ES = json.load(open("evac_summary.json", encoding="utf-8")); X = json.load(open("expo_summary.json", encoding="utf-8"))
C = json.load(open("cve_summary.json", encoding="utf-8")); N = json.load(open("crit_summary.json", encoding="utf-8"))
SH = json.load(open("shrink_summary.json", encoding="utf-8")); SITES = json.load(open("sites.json", encoding="utf-8"))
idx = E["idx"]; anim = E["anim"]; Ta = E["Ta"]
# ---- buildings in the 2026 maximum inundation: page position (0.1 m precision is not needed: 1 m), latest safe departure
#      (T − walk, tenths of a minute) for the city's rule (W) and 1 m/s (F); null where no animation reaches
pts = []
for j, i in enumerate(idx):
    px, py = pgm(B["x"][i], B["y"][i])
    if anim[j]:
        lw = int(round(10 * (Ta[j] - E["walk_W_DH"][j]))); lf = int(round(10 * (Ta[j] - E["walk_F_DH"][j])))
        lw = max(-999, min(999, lw)); lf = max(-999, min(999, lf))
    else:
        lw = lf = None
    pts += [round(px, 2), round(py, 2), lw, lf]
# ---- refuges
sites = [[round(pgm(s["x"], s["y"])[0], 2), round(pgm(s["x"], s["y"])[1], 2), s["name"], int(s["open"]), s["cls_max"], s["safe_2026"],
          s["level_m"], s["muni"]] for s in SITES]
# ---- the medical centre and its warning zone
cz = N["centre_zone"]; zone = None
for ft in json.load(open(cfg.geo("ksj", "A33-25_30Polygon.geojson"), encoding="utf-8"))["features"]:
    if ft["properties"]["A33_004"] == cz["id"]:
        g = tfm(hz.TR, shape(ft["geometry"]).buffer(0)).simplify(3)
        rings = [list(r.coords) for r in ([g.exterior] if g.geom_type == "Polygon" else [p.exterior for p in g.geoms])]
        zone = d_of([[pgm(x, y) for x, y in r] for r in rings], 2) + "z"
spof = [[round(pgm(*hz.TR(*s["lonlat"]))[0], 2), round(pgm(*hz.TR(*s["lonlat"]))[1], 2), s["pop"], s["p65"], s["ref"], s["name"], s["hazard"]] for s in N["spof_top"][:8]]
def g(d, *ks):
    for k in ks: d = d[k]
    return d
SC = {f'{r["model"]}_{r["refuges"]}_{r["depart"]}': r for r in ES["scenarios"]}
stats = {
    # evacuation
    "ev_people": ES["people"], "ev_p65": ES["p65"], "ev_buildings": ES["n_buildings"],
    "ev_groups": ES["groups"], "ev": {k: {g_: v[g_] for g_ in ("Shingu_anim", "Shingu_noanim", "Kiho_anim", "Kiho_noanim", "Shingu_anim_cityTiming15")} for k, v in SC.items()},
    "ev_ouji": ES["ouji_kumanoji"], "ev_kiho_lsd_q": ES["kiho_latest_departure_q"], "ev_kiho_lsd_below": ES["kiho_people_latest_departure_below"],
    "ev_shingu_lsd_q": ES["shingu_latest_departure_q"], "ev_load": ES["load_W_DH"], "ev_places": ES["places"],
    "sites": {"shingu": sum(1 for s in SITES if s["muni"] == 1), "kiho": sum(1 for s in SITES if s["muni"] == 2),
              "shingu_inside": sum(1 for s in SITES if s["muni"] == 1 and s["cls_max"] > 0), "kiho_inside": sum(1 for s in SITES if s["muni"] == 2 and s["cls_max"] > 0),
              "shingu_inside_above": sum(1 for s in SITES if s["muni"] == 1 and s["cls_max"] > 0 and s["safe_2026"] == "yes"),
              "with_level": sum(1 for s in SITES if s["level_m"] is not None)},
    # exposure
    "expo": X, "cve": C, "net": {k: N[k] for k in ("network", "closed_km", "scen", "spof_count_ge10", "replay2011", "centre_reach", "centre_routes", "centre_zone")},
    "shrink": SH,
}
# ---- derived figures the text quotes: tier rows (residents, share aged 65+, share of the town), shares
def tier_rows(x):
    def s(d, *ks): return {"people": sum(d[k]["people"] for k in ks), "p65": sum(d[k]["p65"] for k in ks)}
    R = {"total": x["total"], "ts_l1": x["tsunami_freq"]["any"], "ts_max": x["tsunami_max"]["any"], "ts_max_3m": s(x["tsunami_max"], "3-5", ">=5"),
         "fl_l1": x["flood_L1"]["any"], "fl_l1_05": s(x["flood_L1"], "0.5-3", "3-5", ">=5"), "fl_l2": x["flood_L2"]["any"],
         "fl_l2_3m": s(x["flood_L2"], "3-5", ">=5"), "fl_l2_3d": x["flood_L2_duration"][">=3d"], "collapse": x["house_collapse"]["either"],
         "ls_red": x["landslide"]["red"], "ls_yel": x["landslide"]["yellow_only"], "u_l2": x["union"]["L2_tsunami_or_flood"], "u_all": x["union"]["L2_or_landslide"]}
    T = x["total"]["people"]
    return {k: {"people": v["people"], "p65": v["p65"], "pct65": round(100 * v["p65"] / v["people"], 1) if v["people"] else None,
                "pct_town": round(100 * v["people"] / T, 1)} for k, v in R.items()}
stats["tiers"] = {"Shingu": tier_rows(X["Shingu"]), "Kiho": tier_rows(X["Kiho"])}
stats["tiers"]["Kiho"]["ts_l1"] = None                     # Mie publishes no frequent-class map for Kihō
def pc(a, b): return round(100 * a / b, 1)
K5 = SC["W_DH_5"]["Kiho_anim"][0]; KN = ES["groups"]["Kiho_anim"]["people"]
stats["ev_share"] = {"kiho_W_DH_5": pc(K5, KN), "kiho_F_DH_5": pc(SC["F_DH_5"]["Kiho_anim"][0], KN),
                     "kiho_W_DH_10": pc(SC["W_DH_10"]["Kiho_anim"][0], KN), "kiho_F_DH_10": pc(SC["F_DH_10"]["Kiho_anim"][0], KN)}
fl = N["scen"]["floodL2"]["any_hospital"]
stats["net_share"] = {"floodL2_cut_of_not_direct": {m: pc(fl[m]["cut_off"], X[m]["total"]["people"] - fl[m]["direct"]) for m in ("Shingu", "Kiho")}}
kg = N["replay2011"]["kumanogawa"]
stats["net_replay_delta_min"] = round(kg["replay_mean_min_reachable"] - kg["base_mean_min"], 1)
stats["shrink_decline75"] = {nm: round(100 * (1 - SH["ipss"][c]["75plus"]["2050"] / SH["ipss"][c]["75plus"]["2020"]), 1) for nm, c in (("Shingu", "30207"), ("Kiho", "24562"))}
out = {"pts": pts, "sites": sites, "centre": {"pt": [round(v, 2) for v in pgm(*hz.TR(*N["hospitals"]["新宮市立医療センター"]))], "zone": zone}, "spof": spof, "stats": stats}
js = "window.__RISK = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(os.path.join(K, "data", "risk.js"), "w", encoding="utf-8").write(js)
print("risk.js", round(len(js) / 1024, 1), "KB;", len(idx), "buildings,", len(sites), "sites")
