"""Road-network criticality, Shingū and Kihō, under hazard scenarios.
Network: OpenStreetMap drivable ways, 2026-10-01 (motorways to residential and service roads), 33.60–33.90 N × 135.70–136.06 E;
speeds as the main build (motorway 70 km/h, trunk 45, primary 35, secondary 30, tertiary 25, other 20).
Destinations: the three emergency-designated hospitals of 国土数値情報 P04 (2020) in reach — 新宮市立医療センター (Kōyō),
紀南病院 (御浜町), 那智勝浦町立温泉病院 — and the medical centre alone (the Kōyō hub).
A link closes in a scenario when any point on it (every 10 m; bridges and tunnels exempt) lies in:
  tsunami  2026 maximum class, 0.3 m or deeper (Wakayama R8 / Mie 2026)
  floodL2  A31b-25 maximum flood 0.5 m or deeper;  floodL1  planned-scale flood 0.5 m or deeper
  slideR   土砂災害特別警戒区域 (A33-25);  slideY  any 土砂災害警戒区域
  nankai   tsunami + slideR;  typhoon  floodL2 + slideR;  typhoonY  floodL2 + slideY
Residents: bld.npz (2020 census by building), attached to the nearest drivable vertex."""
import json, glob, math, sys, collections, numpy as np
import shapefile, rasterio.features, affine
from shapely.geometry import shape
from shapely.ops import transform as tfm
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
import hz
import cfg
d = json.load(open(cfg.ROADS))
SPEED = {"motorway": 70, "motorway_link": 40, "trunk": 45, "trunk_link": 30, "primary": 35, "primary_link": 30, "secondary": 30,
         "secondary_link": 25, "tertiary": 25, "tertiary_link": 20, "unclassified": 20, "residential": 20, "living_street": 15, "service": 15, "road": 20}
nid = {}; X = []; Y = []; U = []; V = []; LEN = []; SPD = []; EX = []; REF = []; NAME = []; WAY = []; HW = []
def node(n, lon, lat):
    if n not in nid: nid[n] = len(X); x, y = hz.TR(lon, lat); X.append(x); Y.append(y)
    return nid[n]
for e in d["elements"]:
    if e.get("type") != "way" or not e.get("geometry"): continue
    t = e.get("tags", {}); hw = t.get("highway")
    if hw not in SPEED: continue
    if hw == "service" and t.get("service") in ("parking_aisle", "driveway", "drive-through"): continue
    if t.get("access") in ("no", "private") or t.get("motor_vehicle") in ("no", "private") or t.get("motorcar") in ("no", "private"): continue
    g = e["geometry"]; ns = e.get("nodes")
    if not ns or len(ns) != len(g): continue
    ex = t.get("bridge") not in (None, "no") or t.get("tunnel") not in (None, "no")
    ids = [node(n, p["lon"], p["lat"]) for n, p in zip(ns, g)]
    for a, b in zip(ids, ids[1:]):
        if a == b: continue
        U.append(a); V.append(b); SPD.append(SPEED[hw]); EX.append(ex); REF.append(t.get("ref", "")); NAME.append(t.get("name", "")); WAY.append(e["id"]); HW.append(hw)
X = np.array(X); Y = np.array(Y); U = np.array(U); V = np.array(V); SPD = np.array(SPD, float); EX = np.array(EX); HW = np.array(HW)
MOTOR = np.isin(HW, ("motorway", "motorway_link"))
L = np.hypot(X[U] - X[V], Y[U] - Y[V]); TT = L / (SPD / 3.6) / 60.0          # minutes
nn = len(X)
print("drive vertices", nn, "edges", len(U), "km", round(L.sum() / 1000), file=sys.stderr)
# ---------------- hazard rasters on a 5 m grid over the network
x0, y0, x1, y1 = X.min() - 50, Y.min() - 50, X.max() + 50, Y.max() + 50; RES = 5.0
W = int((x1 - x0) / RES) + 1; H = int((y1 - y0) / RES) + 1; T = affine.Affine(RES, 0, x0, 0, -RES, y1)
def ras_mesh(folder, minrank):
    out = np.zeros((H, W), bool)
    for f in glob.glob(cfg.geo("ksj", "A31b-25", folder, "*.shp")):
        r = shapefile.Reader(f[:-4], encoding="cp932"); gs = []
        for sr in r.iterShapeRecords():
            b = sr.shape.bbox
            if b[2] < 135.69 or b[0] > 136.07 or b[3] < 33.59 or b[1] > 33.91: continue
            if sr.record[0] >= minrank: gs.append(tfm(hz.TR, shape(sr.shape.__geo_interface__)))
        if gs: out |= rasterio.features.rasterize([(g, 1) for g in gs], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0
    return out
FL2 = ras_mesh("20_想定最大規模", 2); FL1 = ras_mesh("10_計画規模", 2)
red = []; yel = []
for f in (cfg.geo("ksj", "A33-25_30Polygon.geojson"), cfg.geo("ksj", "A33-25_24Polygon.geojson")):
    for ft in json.load(open(f, encoding="utf-8"))["features"]:
        b = shape(ft["geometry"]).bounds
        if b[2] < 135.69 or b[0] > 136.07 or b[3] < 33.59 or b[1] > 33.91: continue
        (red if ft["properties"]["A33_002"] in (2, 4) else yel).append(tfm(hz.TR, shape(ft["geometry"]).buffer(0)))
LR = rasterio.features.rasterize([(g, 1) for g in red], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0
LY = LR | (rasterio.features.rasterize([(g, 1) for g in yel], out_shape=(H, W), transform=T, fill=0, dtype="uint8") > 0)
# sample every edge every 10 m
k = np.maximum(1, np.ceil(L / 10).astype(int))
eid = np.repeat(np.arange(len(U)), k + 1); fr = np.concatenate([np.linspace(0, 1, kk + 1) for kk in k])
px = X[U][eid] + (X[V][eid] - X[U][eid]) * fr; py = Y[U][eid] + (Y[V][eid] - Y[U][eid]) * fr
col = ((px - x0) / RES).astype(int); row = ((y1 - py) / RES).astype(int)
def flag(R):
    v = R[row.clip(0, H - 1), col.clip(0, W - 1)]
    out = np.zeros(len(U), bool); np.logical_or.at(out, eid, v); return out & ~EX
pm = hz.muni_of(px, py)
ts = np.zeros(len(U), bool); np.logical_or.at(ts, eid, hz.tsunami_max(px, py, pm) >= 2); ts &= ~EX
F = {"tsunami": ts, "floodL2": flag(FL2), "floodL1": flag(FL1), "slideR": flag(LR), "slideY": flag(LY)}
F["nankai"] = F["tsunami"] | F["slideR"]; F["typhoon"] = F["floodL2"] | F["slideR"]; F["typhoonY"] = F["floodL2"] | F["slideY"]
F["typhoon_motorway_open"] = F["typhoon"] & ~MOTOR; F["floodL2_motorway_open"] = F["floodL2"] & ~MOTOR
for kname, v in F.items(): print("closed links", kname, int(v.sum()), "km", round(L[v].sum() / 1000, 1), file=sys.stderr)
# ---------------- residents and destinations
B = np.load("bld.npz", allow_pickle=True); keep = (B["muni"] > 0) & (B["pop"] > 0)
bx, by, bpop, b65, bmu = B["x"][keep], B["y"][keep], B["pop"][keep], B["p65"][keep], B["muni"][keep]
EXq = np.load("expo.npz")
DIRECT = {"tsunami": EXq["tsm"][keep] >= 2, "floodL2": EXq["fl2"][keep] >= 2, "floodL1": EXq["fl1"][keep] >= 2,
          "slideR": EXq["ls_red"][keep], "slideY": EXq["ls_red"][keep] | EXq["ls_yel"][keep]}
DIRECT["nankai"] = DIRECT["tsunami"] | DIRECT["slideR"]; DIRECT["typhoon"] = DIRECT["floodL2"] | DIRECT["slideR"]; DIRECT["typhoonY"] = DIRECT["floodL2"] | DIRECT["slideY"]
DIRECT["typhoon_motorway_open"] = DIRECT["typhoon"]; DIRECT["floodL2_motorway_open"] = DIRECT["floodL2"]
# attach to the largest component only
_, lab = connected_components(csr_matrix((np.ones(len(U)), (U, V)), shape=(nn, nn)), directed=False)
MAIN = np.nonzero(lab == np.bincount(lab).argmax())[0]
tr = cKDTree(np.c_[X[MAIN], Y[MAIN]]); bd, bi = tr.query(np.c_[bx, by]); bn = MAIN[bi]
# hospitals (P04_001 = 1) designated for emergencies (救急告示, P04_009 = 1) inside the network's area, 国土数値情報 P04 (2020)
import zipfile
HOSP = {}
for zf in ("P04-20_30_GML.zip", "P04-20_24_GML.zip"):
    z = zipfile.ZipFile(cfg.dl("ksj", zf)); n = [x for x in z.namelist() if x.endswith(".geojson")][0]
    for ft in json.loads(z.read(n).decode("utf-8"))["features"]:
        p = ft["properties"]; lo, la = ft["geometry"]["coordinates"]
        if str(p.get("P04_001")) == "1" and str(p.get("P04_009")) == "1" and 135.70 <= lo <= 136.06 and 33.60 <= la <= 33.90:
            HOSP[p["P04_002"]] = (lo, la)
assert set(HOSP) == {"新宮市立医療センター", "紀南病院", "那智勝浦町立温泉病院"}, HOSP
hn = {}
for kname, (lo, la) in HOSP.items():
    hx, hy = hz.TR(lo, la); hn[kname] = MAIN[tr.query([hx, hy])[1]]
def times(closed, dests):
    keepE = ~closed
    G = csr_matrix((np.r_[TT[keepE], TT[keepE]], (np.r_[U[keepE], V[keepE]], np.r_[V[keepE], U[keepE]])), shape=(nn, nn))
    dist = dijkstra(G, directed=False, indices=[hn[k_] for k_ in dests], min_only=True)
    return dist[bn] + bd / (20 / 3.6) / 60.0
base_all = times(np.zeros(len(U), bool), list(HOSP)); base_mc = times(np.zeros(len(U), bool), ["新宮市立医療センター"])
res = {"network": {"vertices": int(nn), "edges": int(len(U)), "km": round(float(L.sum()) / 1000), "osm_base": d["osm3s"]["timestamp_osm_base"]}, "hospitals": {k_: [round(v[0], 7), round(v[1], 7)] for k_, v in HOSP.items()},
       "closed_km": {k_: round(float(L[v].sum()) / 1000, 1) for k_, v in F.items()}, "scen": {}}
def summ(t, tb, direct=None):
    out = {}
    if direct is None: direct = np.zeros(len(t), bool)
    for m, nm in ((1, "Shingu"), (2, "Kiho")):
        km = (bmu == m) & ~direct; cut = km & ~np.isfinite(t)
        fin = km & np.isfinite(t)
        out[nm] = {"direct": round(float(bpop[(bmu == m) & direct].sum())), "cut_off": round(float(bpop[cut].sum())), "cut_off_65": round(float(b65[cut].sum())),
                   "over_30min": round(float(bpop[fin & (t > 30)].sum())), "over_60min": round(float(bpop[fin & (t > 60)].sum())),
                   "mean_min": round(float((t[fin] * bpop[fin]).sum() / bpop[fin].sum()), 1) if bpop[fin].sum() > 0 else None,
                   "mean_delay_min_reachable": round(float(((t - tb)[fin] * bpop[fin]).sum() / bpop[fin].sum()), 2) if bpop[fin].sum() > 0 else None}
    return out
res["scen"]["baseline"] = {"any_hospital": summ(base_all, base_all), "medical_centre": summ(base_mc, base_mc),
                           "medical_centre_within_15": round(float(bpop[base_mc <= 15].sum())), "medical_centre_within_30": round(float(bpop[base_mc <= 30].sum()))}
for kname, closed in F.items():
    tm_ = times(closed, ["新宮市立医療センター"])
    res["scen"][kname] = {"any_hospital": summ(times(closed, list(HOSP)), base_all, DIRECT[kname]), "medical_centre": summ(tm_, base_mc, DIRECT[kname]),
                          "medical_centre_within_15": round(float(bpop[~DIRECT[kname] & (tm_ <= 15)].sum())), "medical_centre_within_30": round(float(bpop[~DIRECT[kname] & (tm_ <= 30)].sum()))}
    # is the medical centre itself reachable from the city hall area? (its own access roads)
    res["scen"][kname]["hospital_access_closed"] = bool(not np.isfinite(times(closed, ["新宮市立医療センター"])[np.argmin(np.hypot(bx - hz.TR(135.992493, 33.724121)[0], by - hz.TR(135.992493, 33.724121)[1]))]))
# ---------------- single points of failure: links whose loss cuts residents off every hospital (graph bridges)
import networkx as nx
Gx = nx.Graph()
for i, (a, b) in enumerate(zip(U, V)):
    if Gx.has_edge(a, b): Gx[a][b]["ids"].append(i)
    else: Gx.add_edge(a, b, ids=[i])
popnode = collections.Counter(); p65node = collections.Counter()
for n_, p_, q_ in zip(bn, bpop, b65): popnode[n_] += p_; p65node[n_] += q_
bridges = [(a, b) for a, b in nx.bridges(Gx) if len(Gx[a][b]["ids"]) == 1]
# component tree: remove all bridges, label 2-edge-connected parts, then subtree sums from the hospitals' part
H2 = Gx.copy(); H2.remove_edges_from(bridges)
comp = {}
for ci, cc in enumerate(nx.connected_components(H2)):
    for v_ in cc: comp[v_] = ci
T2 = nx.Graph()
for a, b in bridges: T2.add_edge(comp[a], comp[b], e=(a, b))
cpop = collections.Counter(); c65 = collections.Counter()
for v_, p_ in popnode.items(): cpop[comp[v_]] += p_; c65[comp[v_]] += p65node[v_]
root = comp[hn["新宮市立医療センター"]]
others = {comp[hn[k_]] for k_ in HOSP}
spof = []
if root in T2:
    parent = dict(nx.bfs_predecessors(T2, root)); order = list(nx.bfs_tree(T2, root))
    sub = {c: cpop[c] for c in order}; sub65 = {c: c65[c] for c in order}; hasH = {c: (c in others) for c in order}
    for c in reversed(order):
        p = parent.get(c)
        if p is not None: sub[p] += sub[c]; sub65[p] += sub65[c]; hasH[p] = hasH[p] or hasH[c]
    for c in order:
        p = parent.get(c)
        if p is None or sub[c] < 1: continue
        a, b = T2[p][c]["e"]; i = Gx[a][b]["ids"][0]
        if not (HW[i] in ("motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified") or REF[i]): continue
        spof.append({"pop": round(float(sub[c])), "p65": round(float(sub65[c])), "other_hospital_beyond": bool(hasH[c]), "ref": REF[i], "name": NAME[i], "way": int(WAY[i]),
                     "lonlat": [round(v, 5) for v in hz.TI((X[a] + X[b]) / 2, (Y[a] + Y[b]) / 2)], "len_m": round(float(L[i])),
                     "hazard": [k_ for k_ in ("tsunami", "floodL2", "floodL1", "slideR", "slideY") if F[k_][i]], "class": HW[i]})
spof.sort(key=lambda s: -s["pop"])
# merge links of the same way (a chain of bridges along one road counts once, at its largest cut)
seen = set(); top = []
for s in spof:
    if s["way"] in seen: continue
    seen.add(s["way"]); top.append(s)
res["spof_top"] = top[:15]
res["spof_count_ge10"] = sum(1 for s in top if s["pop"] >= 10)
# ---------------- 2011 replay: Route 168 between 宮井 and the city, closed 3 Sep – 14 Oct 2011 (city record)
r168 = np.array(["168" in r for r in REF])
mx, my = np.array(hz.TR(135.8492517, 33.8324227)); cx_, cy_ = np.array(hz.TR(135.9295976, 33.7373642))
mid_x = (X[U] + X[V]) / 2; mid_y = (Y[U] + Y[V]) / 2
seg = r168 & (mid_y <= my + 50) & (mid_y >= cy_ - 50) & (mid_x >= mx - 50) & (mid_x <= cx_ + 50)
res["replay2011"] = {"r168_km_removed": round(float(L[seg].sum()) / 1000, 1),
                     "r168_only": summ(times(seg, list(HOSP)), base_all), "r168_only_mc": summ(times(seg, ["新宮市立医療センター"]), base_mc),
                     "r168_plus_typhoonY": summ(times(seg | F["typhoonY"], list(HOSP)), base_all)}
# Kumanogawa-chō residents (small areas named 熊野川町…) under the replay
SA = json.load(open("derived_smallarea_age_2020_shingu_kiho.geojson", encoding="utf-8"))["features"]
san = np.array([SA[j]["properties"]["name"] if j >= 0 else "" for j in B["sa"][keep]])
kk = np.array([s.startswith("熊野川町") for s in san])
t_r = times(seg, ["新宮市立医療センター"])
res["replay2011"]["kumanogawa"] = {"people": round(float(bpop[kk].sum())), "base_mean_min": round(float((base_mc[kk] * bpop[kk]).sum() / bpop[kk].sum()), 1),
                                   "cut_off": round(float(bpop[kk & ~np.isfinite(t_r)].sum())),
                                   "replay_mean_min_reachable": round(float((t_r[kk & np.isfinite(t_r)] * bpop[kk & np.isfinite(t_r)]).sum() / max(1, bpop[kk & np.isfinite(t_r)].sum())), 1)}

print(json.dumps({k_: res[k_] for k_ in ("network", "closed_km")}, ensure_ascii=False))
for k_, v in res["scen"].items(): print(k_, json.dumps(v, ensure_ascii=False))
print("SPOF", json.dumps(res["spof_top"][:10], ensure_ascii=False, indent=0))
print("2011", json.dumps(res["replay2011"], ensure_ascii=False))
# ---------------- how the medical centre is reached: links out of it within the yellow / red zones
Gb = csr_matrix((np.r_[TT, TT], (np.r_[U, V], np.r_[V, U])), shape=(nn, nn))
for nm_, cl in (("slideY", F["slideY"]), ("slideR", F["slideR"]), ("floodL2", F["floodL2"]), ("tsunami", F["tsunami"])):
    ke = ~cl
    G2 = csr_matrix((np.r_[TT[ke], TT[ke]], (np.r_[U[ke], V[ke]], np.r_[V[ke], U[ke]])), shape=(nn, nn))
    dd = dijkstra(G2, directed=False, indices=hn["新宮市立医療センター"])
    reach = np.isfinite(dd)
    res.setdefault("centre_reach", {})[nm_] = {"vertices": int(reach.sum()), "residents": round(float(bpop[reach[bn]].sum()))}
    print("medical centre,", nm_, "closed: reachable vertices", int(reach.sum()), "of", nn, "; residents reachable", round(float(bpop[reach[bn]].sum())))
# baseline shortest-path tree from the centre: the first 1.5 km of every route out, and the zones it crosses
dd0, pr0 = dijkstra(Gb, directed=False, indices=hn["新宮市立医療センター"], return_predecessors=True)
ring = np.nonzero((dd0 > 1.2) & (dd0 < 1.6))[0]
eidx = {}
for i, (a, b) in enumerate(zip(U, V)): eidx[(a, b)] = i; eidx[(b, a)] = i
paths_y = 0; paths = 0; exits = collections.Counter()
for r in ring[:: max(1, len(ring) // 400)]:
    n_ = r; inY = False; first = None
    while n_ != hn["新宮市立医療センター"] and n_ >= 0:
        p_ = pr0[n_]
        if p_ < 0: break
        i = eidx[(p_, n_)]
        if F["slideY"][i]: inY = True
        first = i; n_ = p_
    paths += 1; paths_y += inY
    if first is not None: exits[(REF[first], NAME[first], HW[first])] += 1
res["centre_routes"] = {"sampled": paths, "through_warning_zone_within_1_5_min": paths_y}
print("routes out of the medical centre sampled", paths, "crossing a warning zone within 1.5 min", paths_y)
print("first links used", exits.most_common(5))

# the sediment-disaster warning zone the medical centre stands in (A33-25)
from shapely.geometry import Point as _Pt
_c = hz.TR(*HOSP["新宮市立医療センター"])
for f in (cfg.geo("ksj", "A33-25_30Polygon.geojson"),):
    for ft in json.load(open(f, encoding="utf-8"))["features"]:
        g = tfm(hz.TR, shape(ft["geometry"]).buffer(0))
        if g.contains(_Pt(*_c)):
            p = ft["properties"]; res["centre_zone"] = {"kind": {1: "急傾斜地の崩壊", 2: "土石流", 3: "地すべり"}.get(p["A33_001"]), "warning": p["A33_002"],
                                                        "name": p["A33_005"], "place": p["A33_006"], "designated": p["A33_007"], "id": p["A33_004"]}
json.dump(res, open("crit_summary.json", "w"), ensure_ascii=False, indent=1)
print("centre zone", res.get("centre_zone"))
