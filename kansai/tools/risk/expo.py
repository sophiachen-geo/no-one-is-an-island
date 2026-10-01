"""Hazard per building (both banks) and people by tier.
Tsunami 2026: Wakayama R8 (Shingū; frequent 3連動 and maximum 巨大) and Mie 2026 L2 (Kihō; Mie publishes no L1 map).
River flood: 国土数値情報 A31b-25 (10 m mesh, every river with a published map, national and prefectural merged by
maximum): planned scale (計画規模, L1), maximum (想定最大規模, L2), duration (L2), house-collapse zones (氾濫流, 河岸侵食).
Landslide: A33-25 土砂災害警戒区域 / 特別警戒区域 (Wakayama, Mie), by phenomenon.
Writes expo.npz (per building codes) and expo_summary.json."""
import json, glob, os, sys, collections, numpy as np
import shapefile
from shapely.geometry import shape, Point
from shapely.ops import transform as tfm
from shapely.strtree import STRtree
import hz
B = np.load("bld.npz", allow_pickle=True)
x, y, mu, pop, p65, p75 = B["x"], B["y"], B["muni"], B["pop"], B["p65"], B["p75"]
n = len(x)
import cfg
F = cfg.geo("ksj", "A31b-25")
def mesh_rank(folder, fld):
    """max rank over all A31b files of one theme at every building point"""
    out = np.zeros(n, np.uint8)
    bb = (x.min() - 50, y.min() - 50, x.max() + 50, y.max() + 50)
    for f in glob.glob(f"{F}/{folder}/*.shp"):
        r = shapefile.Reader(f[:-4], encoding="cp932")
        geoms = []; ranks = []
        for sr in r.iterShapeRecords():
            b = sr.shape.bbox
            if b[2] < 135.9 or b[0] > 136.1 or b[3] < 33.6 or b[1] > 33.9: continue
            g = tfm(hz.TR, shape(sr.shape.__geo_interface__))
            geoms.append(g); ranks.append(sr.record[0])
        if not geoms: continue
        t = STRtree(geoms); ranks = np.array(ranks)
        pts = [Point(a, b) for a, b in zip(x, y)]
        bi, gi = t.query(pts, predicate="intersects")
        for i, j in zip(bi, gi):
            if ranks[j] > out[i]: out[i] = ranks[j]
        print(folder, os.path.basename(f), len(geoms), file=sys.stderr)
    return out
fl1 = mesh_rank("10_計画規模", "A31b_101")
fl2 = mesh_rank("20_想定最大規模", "A31b_201")
dur = mesh_rank("30_浸水継続時間", "A31b_301")
hflow = mesh_rank("41_家屋倒壊等氾濫想定区域_氾濫流", "A31b_401")
heros = mesh_rank("42_家屋倒壊等氾濫想定区域_河岸侵食", "A31b_401")
tsm = hz.tsunami_max(x, y, mu); tsf = hz.tsunami_freq(x, y, mu)
# landslide zones
ls_red = np.zeros(n, bool); ls_yel = np.zeros(n, bool); ls_kind = np.zeros(n, np.uint8)
geoms = []; props = []
for f in (cfg.geo("ksj", "A33-25_30Polygon.geojson"), cfg.geo("ksj", "A33-25_24Polygon.geojson")):
    for ft in json.load(open(f, encoding="utf-8"))["features"]:
        c = shape(ft["geometry"]).bounds
        if c[2] < 135.9 or c[0] > 136.1 or c[3] < 33.6 or c[1] > 33.9: continue
        geoms.append(tfm(hz.TR, shape(ft["geometry"]).buffer(0))); props.append(ft["properties"])
t = STRtree(geoms)
bi, gi = t.query([Point(a, b) for a, b in zip(x, y)], predicate="intersects")
for i, j in zip(bi, gi):
    p = props[j]
    if p["A33_002"] in (2, 4): ls_red[i] = True
    else: ls_yel[i] = True
    ls_kind[i] |= {1: 1, 2: 2, 3: 4}.get(p.get("A33_001"), 0)
np.savez_compressed("expo.npz", fl1=fl1, fl2=fl2, dur=dur, hflow=hflow, heros=heros, tsm=tsm, tsf=tsf, ls_red=ls_red, ls_yel=ls_yel, ls_kind=ls_kind)
def agg(mask):
    return {"people": round(float(pop[mask].sum())), "p65": round(float(p65[mask].sum())), "p75": round(float(p75[mask].sum())), "buildings": int((mask & (pop > 0)).sum())}
# tsunami classes -> depth tiers (<0.5, 0.5–3, 3–5, ≥5 m)
def ts_tier(c): return np.select([c == 0, c <= 2, c <= 4, c == 5, c >= 6], [0, 1, 2, 3, 4])
def fl_tier(r): return np.select([r == 0, r == 1, r == 2, r == 3, r >= 4], [0, 1, 2, 3, 4])
S = {}
for m, name in ((1, "Shingu"), (2, "Kiho")):
    k = mu == m
    d = {"total": agg(k)}
    tm = ts_tier(tsm); tf = ts_tier(np.where(tsf == 255, 0, tsf)); f1 = fl_tier(fl1); f2 = fl_tier(fl2)
    for lab, arr in (("tsunami_max", tm), ("tsunami_freq", tf), ("flood_L1", f1), ("flood_L2", f2)):
        d[lab] = {t_: agg(k & (arr == i)) for i, t_ in ((1, "<0.5"), (2, "0.5-3"), (3, "3-5"), (4, ">=5"))}
        d[lab]["any"] = agg(k & (arr > 0))
    d["flood_L2_duration"] = {t_: agg(k & np.isin(dur, v)) for t_, v in (("<24h", (1, 2)), ("1-3d", (3,)), (">=3d", (4, 5, 6, 7)))}
    d["house_collapse"] = {"flow": agg(k & (hflow > 0)), "erosion": agg(k & (heros > 0)), "either": agg(k & ((hflow > 0) | (heros > 0)))}
    d["landslide"] = {"red": agg(k & ls_red), "yellow_only": agg(k & ls_yel & ~ls_red), "any": agg(k & (ls_red | ls_yel)), "debris_flow": agg(k & ((ls_kind & 2) > 0))}
    L1 = (tf > 0) | (f1 > 0); L2 = (tm > 0) | (f2 > 0)
    d["union"] = {"L1_tsunami_or_flood": agg(k & L1), "L2_tsunami_or_flood": agg(k & L2),
                  "L2_or_landslide": agg(k & (L2 | ls_red | ls_yel)),
                  "deep_3m_L2": agg(k & ((tm >= 3) | (f2 >= 3))), "half_m_L1": agg(k & ((tf >= 2) | (f1 >= 2))),
                  "tsunami_and_flood_L2": agg(k & (tm > 0) & (f2 > 0))}
    S[name] = d
json.dump(S, open("expo_summary.json", "w"), ensure_ascii=False, indent=1)
for name in S:
    d = S[name]; print(name, "total", d["total"])
    for lab in ("tsunami_freq", "tsunami_max", "flood_L1", "flood_L2"): print(" ", lab, {k_: v["people"] for k_, v in d[lab].items()}, "65+ any", d[lab]["any"]["p65"])
    print("  duration", {k_: v["people"] for k_, v in d["flood_L2_duration"].items()}, "house", {k_: v["people"] for k_, v in d["house_collapse"].items()})
    print("  landslide", {k_: v["people"] for k_, v in d["landslide"].items()})
    print("  union", {k_: (v["people"], v["p65"]) for k_, v in d["union"].items()})
