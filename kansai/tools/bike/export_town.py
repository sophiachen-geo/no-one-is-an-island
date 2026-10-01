import json, os, sys, math, collections, re
from pyproj import Transformer
from pagegeo import pgm, pg, d_of, simp, fm
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
H = os.getcwd()
T = json.load(open(os.path.join(H, "town", "town_out.json")))
roads = json.load(open(os.path.join(H, "roads.json")))
import town as TW            # re-runs the town analysis (networks) - cheap enough and keeps one source of truth
# networks: one path per mode (ways inside the core frame)
CORE = TW.CORE
nets = {}
for mode in ("walk", "bike", "car"):
    lines = []
    for wid, e in TW.ways.items():
        t = e.get("tags", {})
        if not TW.mode_ok(mode, t, TW.wclass[wid]): continue
        g = e["geometry"]
        if not any(CORE[0] - .002 <= q["lon"] <= CORE[2] + .002 and CORE[1] - .002 <= q["lat"] <= CORE[3] + .002 for q in g): continue
        lines.append([pg(q["lon"], q["lat"]) for q in g])
    nets[mode] = d_of([simp(l, 0.01) for l in lines], 2)
# building dots: page units, 2 decimals; directness x100 (0 = no access within 60 m)
B = T["B"]; Dd = T["dir"]
dots = []
for i, (x, y) in enumerate(B):
    px, py = pgm(x, y)
    vals = [0 if Dd[m][i] is None else (-1 if Dd[m][i] < 0 else int(round(Dd[m][i] * 100))) for m in ("walk", "bike", "car")]
    dots.append([round(px, 2), round(py, 2)] + vals)
# ride legs
legs = []
for L in T["legs"]:
    pts = [pgm(x, y) for x, y in L["xy"]]
    legs.append({"from": L["from"], "to": L["to"], "t0": L["t0"][11:16], "t1": L["t1"][11:16], "len": L["len_m"], "up": L["up"], "snap": L["snap_m"], "d": d_of([simp(pts, 0.01)], 2),
                 "rows": [[r["s"], r["w"], r["ctg"], r["hw"], r["shops"], int(r["sacred"]), int(r["water"]), r["front"], r["h"], r["name"] or r["ref"] or ""] for r in L["rows"]]})
json.dump({"nets": nets, "dots": dots, "legs": legs, "sites": T["sites"]}, open(os.path.join(H, "fn_town.json"), "w"), ensure_ascii=False)
print("town export:", {k: len(json.dumps(v, ensure_ascii=False)) // 1024 for k, v in (("nets", nets), ("dots", dots), ("legs", legs))}, "KB", file=sys.stderr)
