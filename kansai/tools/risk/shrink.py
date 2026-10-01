"""2050: the evacuation margins with the population the IPSS projects (日本の地域別将来推計人口, 令和5年推計).
Residents under 75 walk at CAO 2025's speed for all walkers (model C), residents 75 and over at its speed for people walking
with someone who needs help (model E); departure 5 min, refuges D + high ground. In 2050 every building keeps its 2020
people, scaled by the town's projected change for each of the two age groups.
Writes shrink_summary.json."""
import json, numpy as np, openpyxl
import cfg
def ipss(fn):
    out = {}
    ws = openpyxl.load_workbook(cfg.dl("ipss2023", fn), read_only=True, data_only=True).worksheets[0]
    for row in ws.iter_rows(values_only=True):
        if row and row[0] in (30207, 24562): out[row[0]] = {2020: row[4], 2050: row[10]}
    return out
TOT = ipss("kekkahyo1.xlsx"); A75 = ipss("kekkahyo2_4.xlsx")
B = np.load("bld.npz", allow_pickle=True); E = np.load("evac.npz", allow_pickle=True)
idx = E["idx"]; anim = E["anim"]; Ta = E["Ta"]; mu = B["muni"][idx]; pop = B["pop"][idx]; p75 = B["p75"][idx]; lt75 = pop - p75
fC = (Ta - 5 - E["walk_C_DH"]) < 0; fE = (Ta - 5 - E["walk_E_DH"]) < 0
out = {"ipss": {str(k): {"total": TOT[k], "75plus": A75[k]} for k in TOT}}
for m, nm, code in ((1, "Shingu", 30207), (2, "Kiho", 24562)):
    k = (mu == m) & anim
    t20, t50 = TOT[code][2020], TOT[code][2050]; a20, a50 = A75[code][2020], A75[code][2050]
    fl = (t50 - a50) / (t20 - a20); fa = a50 / a20
    f20 = (lt75[k] * fC[k]).sum() + (p75[k] * fE[k]).sum(); n20 = pop[k].sum()
    f50 = (lt75[k] * fl * fC[k]).sum() + (p75[k] * fa * fE[k]).sum(); n50 = (lt75[k] * fl).sum() + (p75[k] * fa).sum()
    out[nm] = {"2020": {"in_zone": round(float(n20)), "fail": round(float(f20)), "share": round(100 * float(f20 / n20), 1), "share75": round(100 * float(p75[k].sum() / n20), 1)},
               "2050": {"in_zone": round(float(n50)), "fail": round(float(f50)), "share": round(100 * float(f50 / n50), 1), "share75": round(100 * float((p75[k] * fa).sum() / n50), 1)},
               "factors": {"under75": round(fl, 3), "75plus": round(fa, 3)}}
json.dump(out, open("shrink_summary.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
