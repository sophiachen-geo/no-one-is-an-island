"""Concentrate versus evacuate: Shingū's 立地適正化計画 zones (MLIT A55, FY2024: 居住誘導区域, 都市機能誘導区域) against
the hazard tiers, by area (2 m grid) and by residents (expo.npz, bld.npz), plus the evacuation margins (evac.npz)."""
import json, glob, sys, numpy as np
import shapefile, rasterio.features, affine
from shapely.geometry import shape, Point
from shapely.ops import unary_union, transform as tfm
from shapely.prepared import prep
from pyproj import Transformer
import hz
import cfg
R = json.load(open(cfg.geo("ksj", "A55-24_30207_GEOJSON", "30207_ritteki.geojson"), encoding="utf-8"))["features"]
RIZ = unary_union([tfm(hz.TR, shape(f["geometry"]).buffer(0)) for f in R if f["properties"]["AreaType"] == "居住誘導区域"])
PLAN = unary_union([tfm(hz.TR, shape(f["geometry"]).buffer(0)) for f in R if f["properties"]["AreaType"] == "立地適正化計画区域"])
UFs = [tfm(hz.TR, shape(f["geometry"]).buffer(0)) for f in R if f["properties"]["AreaType"] == "都市機能誘導区域"]
UF = {}
for g in UFs:
    lon, lat = hz.TI(g.centroid.x, g.centroid.y)
    UF["centre" if lat > 33.71 else ("koyo_medical" if lon < 135.975 else "miwasaki")] = g
ZONES = {"residential (RIZ)": RIZ, **{f"function: {k}": v for k, v in UF.items()}, "plan area": PLAN}
# 2 m grid over the plan area
x0, y0, x1, y1 = PLAN.bounds; RES = 2.0
W = int((x1 - x0) / RES) + 1; H = int((y1 - y0) / RES) + 1
T = affine.Affine(RES, 0, x0, 0, -RES, y1)
cx = x0 + (np.arange(W) + 0.5) * RES; cy = y1 - (np.arange(H) + 0.5) * RES
GX, GY = np.meshgrid(cx, cy)
print("grid", H, W, file=sys.stderr)
mu = np.ones_like(GX, dtype=int)                 # the plan area lies in Shingū
tsm = hz.tsunami_max(GX.ravel(), GY.ravel(), mu.ravel()).reshape(H, W)
tsf = hz.tsunami_freq(GX.ravel(), GY.ravel(), mu.ravel()).reshape(H, W)
def mesh_raster(folder):
    out = np.zeros((H, W), np.uint8)
    for f in glob.glob(cfg.geo("ksj", "A31b-25", folder, "*.shp")):
        r = shapefile.Reader(f[:-4], encoding="cp932"); shapes = []
        for sr in r.iterShapeRecords():
            b = sr.shape.bbox
            if b[2] < 135.9 or b[0] > 136.06 or b[3] < 33.66 or b[1] > 33.80: continue
            shapes.append((tfm(hz.TR, shape(sr.shape.__geo_interface__)), int(sr.record[0])))
        if shapes:
            # one rank at a time so the maximum wins
            for rk in sorted(set(v for _, v in shapes)):
                a = rasterio.features.rasterize([(g, 1) for g, v in shapes if v == rk], out_shape=(H, W), transform=T, fill=0, dtype="uint8")
                out = np.where(a > 0, np.maximum(out, rk), out)
    return out
fl1 = mesh_raster("10_計画規模"); fl2 = mesh_raster("20_想定最大規模"); dur = mesh_raster("30_浸水継続時間")
hc = np.maximum(mesh_raster("41_家屋倒壊等氾濫想定区域_氾濫流"), mesh_raster("42_家屋倒壊等氾濫想定区域_河岸侵食"))
red = []; yel = []
for f in (cfg.geo("ksj", "A33-25_30Polygon.geojson"),):
    for ft in json.load(open(f, encoding="utf-8"))["features"]:
        b = shape(ft["geometry"]).bounds
        if b[2] < 135.9 or b[0] > 136.06 or b[3] < 33.66 or b[1] > 33.80: continue
        (red if ft["properties"]["A33_002"] in (2, 4) else yel).append(tfm(hz.TR, shape(ft["geometry"]).buffer(0)))
LR = rasterio.features.rasterize([(g, 1) for g in red], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0
LY = rasterio.features.rasterize([(g, 1) for g in yel], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0
layers = {"tsunami_max_any": tsm > 0, "tsunami_max_0.3m": tsm >= 2, "tsunami_max_3m": tsm >= 5, "tsunami_freq_any": (tsf > 0) & (tsf < 255),
          "flood_L1_any": fl1 > 0, "flood_L1_0.5m": fl1 >= 2, "flood_L2_any": fl2 > 0, "flood_L2_3m": fl2 >= 3,
          "flood_L2_24h": dur >= 3, "flood_L2_72h": dur >= 4, "house_collapse": hc > 0, "landslide_red": LR, "landslide_yellow": LY,
          "L1_union": ((tsf > 0) & (tsf < 255)) | (fl1 > 0), "L2_union": (tsm > 0) | (fl2 > 0),
          "deep_union": (tsm >= 5) | (fl2 >= 3), "L2_union_or_landslide": (tsm > 0) | (fl2 > 0) | LR | LY}
out = {"area": {}, "people": {}}
for zn, zg in ZONES.items():
    zm = rasterio.features.rasterize([(zg, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0
    out["area"][zn] = {"ha": round(float(zm.sum()) * RES * RES / 1e4, 1), **{k: round(100 * float((v & zm).sum()) / max(1, zm.sum()), 1) for k, v in layers.items()}}
# residents
B = np.load("bld.npz", allow_pickle=True); E = np.load("expo.npz")
bx, by, pop, p65 = B["x"], B["y"], B["pop"], B["p65"]
bl = {"tsunami_max_any": E["tsm"] > 0, "tsunami_max_0.3m": E["tsm"] >= 2, "tsunami_max_3m": E["tsm"] >= 5, "tsunami_freq_any": (E["tsf"] > 0) & (E["tsf"] < 255),
      "flood_L1_any": E["fl1"] > 0, "flood_L1_0.5m": E["fl1"] >= 2, "flood_L2_any": E["fl2"] > 0, "flood_L2_3m": E["fl2"] >= 3,
      "flood_L2_24h": E["dur"] >= 3, "flood_L2_72h": E["dur"] >= 4, "house_collapse": (E["hflow"] > 0) | (E["heros"] > 0),
      "landslide_red": E["ls_red"], "landslide_yellow": E["ls_yel"] & ~E["ls_red"]}
bl["L1_union"] = bl["tsunami_freq_any"] | bl["flood_L1_any"]; bl["L2_union"] = bl["tsunami_max_any"] | bl["flood_L2_any"]
bl["deep_union"] = bl["tsunami_max_3m"] | bl["flood_L2_3m"]; bl["L2_union_or_landslide"] = bl["L2_union"] | E["ls_red"] | E["ls_yel"]
EV = np.load("evac.npz", allow_pickle=True)
fail = np.zeros(len(bx), bool)
mg = EV["Ta"] - 5 - EV["walk_W_DH"]
fail[EV["idx"][EV["anim"] & (mg < 0)]] = True
fail_noanim = np.zeros(len(bx), bool); fail_noanim[EV["idx"][~EV["anim"]]] = True
# the city's timing (first water by 15 min at the latest, as Shingū still plans for 王子・熊野地), same walk
fail15 = np.zeros(len(bx), bool); fail15[EV["idx"][EV["anim"] & ((np.minimum(EV["Ta"], 15.0) - 5 - EV["walk_W_DH"]) < 0)]] = True
bl["tsunami_margin_negative_anim"] = fail; bl["tsunami_margin_negative_city15"] = fail15; bl["tsunami_no_arrival_data"] = fail_noanim
for zn, zg in ZONES.items():
    P = prep(zg); inz = np.array([P.contains(Point(a, b)) for a, b in zip(bx, by)])
    tot = pop[inz].sum()
    out["people"][zn] = {"people": round(float(tot)), "p65": round(float(p65[inz].sum())),
                         **{k: [round(float(pop[inz & v].sum())), round(100 * float(pop[inz & v].sum()) / max(1, tot), 1)] for k, v in bl.items()}}
json.dump(out, open("cve_summary.json", "w"), ensure_ascii=False, indent=1)
for zn in ZONES:
    a = out["area"][zn]; p = out["people"][zn]
    print(zn, "ha", a["ha"], "people", p["people"])
    print("  area %:", {k: a[k] for k in ("L1_union", "L2_union", "deep_union", "tsunami_max_any", "tsunami_freq_any", "flood_L1_any", "flood_L2_any", "house_collapse", "landslide_red", "landslide_yellow", "L2_union_or_landslide")})
    print("  people %:", {k: p[k][1] for k in ("L1_union", "L2_union", "deep_union", "tsunami_max_any", "flood_L1_any", "flood_L2_any", "house_collapse", "landslide_red", "landslide_yellow", "tsunami_margin_negative_anim", "tsunami_no_arrival_data")})
