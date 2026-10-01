"""Tsunami evacuation margin for every inhabited building in the 2026 maximum-class inundation of Shingū and Kihō.

margin = T_arrival − t_depart − t_walk(to the refuge reached first) − t_climb
T_arrival  first wetting (≈1 cm) at the building in Wakayama's R8 animation of Shingū (巨大), registered to the map
           (tools/tsunami2026). Where the animation does not reach (三輪崎・佐野; Kihō north of its frame) two bounds,
           6 and 10 min: Shingū's own range for 三輪崎 (H25 programme, 6–10 min) and Mie's +1 m at 井田 (6 min).
t_depart   5 min (Wakayama, Shingū, CAO daytime), 10 (CAO night), 15 (CAO 用事後避難).
t_walk     shortest time on the walking network (walknet.py); speed models
             W  Wakayama/Shingū rule: 0.5 m/s (30 m/min) on ways, 0.35 m/s (21 m/min) straight to the network
             C  CAO 2025, all walkers: 0.70 m/s below 5 % grade, 0.44 m/s at 5 % or more
             E  CAO 2025, walking with a person who needs help: 0.53 / 0.33 m/s
             F  FDMA guideline: 1.0 m/s
           steps take at least rise / 0.21 m/s (the MLIT and Wakayama stair rate) in every model.
t_climb    to the floor the city lists (2017), or above the 2026 depth class where no floor is listed, at 0.21 m/s.
Refuges    D  designated tsunami sites (GSI 指定緊急避難場所 with 津波, updated 2025-01-23; sites.py)
           DH D + ground at or above the maximum tsunami height (Shingū 13 m, Kihō 11 m) outside the inundation
              (Wakayama's programme: 「巨大地震による最大津波高よりも高い場所への避難を前提とする」).
Sensitivity 'city timing': R8 treats road and railway embankments as terrain that does not fail, and the animation wets
Shingū's inner lowland late; T is capped at 15 min, the upper end of the 1 cm arrival Shingū still plans with for
王子・熊野地 (H25: 7–15 min).
Also: the refuge each building reaches first, people per refuge, latest safe departure = T − t_walk.
Writes evac_summary.json and evac.npz."""
import json, sys, itertools, collections, numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
import hz
import os
B = np.load("bld.npz", allow_pickle=True); N = np.load("walknet.npz")
x, y, mu, pop, p65, p75, sa = B["x"], B["y"], B["muni"], B["pop"], B["p65"], B["p75"], B["sa"]
cls = hz.tsunami_max(x, y, mu)
idx = np.nonzero((cls > 0) & (pop > 0))[0]
Ta, inframe = hz.arrival("kyodai", x[idx], y[idx])
anim = ~np.isnan(Ta)
SA = json.load(open("derived_smallarea_age_2020_shingu_kiho.geojson", encoding="utf-8"))["features"]
sa_name = np.array([SA[j]["properties"]["name"] if j >= 0 else "" for j in sa[idx]])
nx_, ny_, nz_ = N["x"], N["y"], N["z"]; U, V, L, RISE, ST = N["u"], N["v"], N["length"], N["rise"], N["steps"]
nn = len(nx_); grade = RISE / np.maximum(L, 10.0)
MODELS = {"W": (0.5, 0.5, 0.35), "C": (0.70, 0.44, 0.70), "E": (0.53, 0.33, 0.53), "F": (1.0, 1.0, 1.0)}
S = json.load(open("sites.json"))
sx = np.array([s["x"] for s in S]); sy = np.array([s["y"] for s in S]); climb = np.array([s["climb_m"] for s in S])
# buildings and refuges attach to the main connected network only (small fragments far inland, or a few lanes GSI
# draws without a junction, would otherwise strand them)
from scipy.sparse.csgraph import connected_components
_k, _lab = connected_components(csr_matrix((np.ones(len(U)), (U, V)), shape=(nn, nn)), directed=False)
MAIN = np.nonzero(_lab == np.bincount(_lab).argmax())[0]
_t = cKDTree(np.c_[nx_[MAIN], ny_[MAIN]])
class _T:
    def query(self, P):
        d, i = _t.query(P); return d, MAIN[i]
tree = _T(); sd, sn = tree.query(np.c_[sx, sy])
node_mu = hz.muni_of(nx_, ny_); node_cls = hz.tsunami_max(nx_, ny_, node_mu)
high = (((node_mu == 1) & (nz_ >= 13.0)) | ((node_mu == 2) & (nz_ >= 11.0))) & (node_cls == 0)
bd, bn = tree.query(np.c_[x[idx], y[idx]])
DIST = {}
def solve(m, tg):
    vf, vs, va = MODELS[m]
    w = np.where(grade < 0.05, L / vf, L / vs); w = np.where(ST, np.maximum(w, RISE / 0.21), w)
    rows = [U, V]; cols = [V, U]; data = [w, w]
    # one virtual node per refuge so the path tells which refuge was reached: nn + k for site k, nn + len(S) for high ground
    for k in range(len(S)):
        rows.append([nn + k]); cols.append([sn[k]]); data.append([sd[k] / va + climb[k] / 0.21 + 1e-6])
    root = nn + len(S) + 1
    rows.append(np.full(len(S), root)); cols.append(np.arange(nn, nn + len(S))); data.append(np.full(len(S), 1e-6))
    if tg == "DH":
        hn = np.nonzero(high)[0]
        rows.append(np.full(len(hn), nn + len(S))); cols.append(hn); data.append(np.full(len(hn), 1e-6))
        rows.append([root]); cols.append([nn + len(S)]); data.append([1e-6])
    G = csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))), shape=(root + 1, root + 1))
    dist, pred = dijkstra(G, directed=True, indices=root, return_predecessors=True)
    walk = (bd / va + dist[bn]) / 60.0
    DIST[(m, tg)] = dist
    # refuge per building: walk back to the virtual layer
    ref = np.full(len(idx), -9)
    for i, n0 in enumerate(bn):
        n = n0; guard = 0
        while n >= 0 and n < nn and guard < 100000: n = pred[n]; guard += 1
        ref[i] = (n - nn) if n >= nn else -9           # 0..len(S)-1 = site; len(S) = high ground
    return walk, ref
out = {"n_buildings": int(len(idx)), "people": round(float(pop[idx].sum())), "p65": round(float(p65[idx].sum())), "p75": round(float(p75[idx].sum()))}
groups = {"Shingu_anim": (mu[idx] == 1) & anim, "Shingu_noanim": (mu[idx] == 1) & ~anim, "Kiho_anim": (mu[idx] == 2) & anim, "Kiho_noanim": (mu[idx] == 2) & ~anim}
out["groups"] = {g: {"buildings": int(k.sum()), "people": round(float(pop[idx][k].sum())), "p65": round(float(p65[idx][k].sum())),
                     "arrival_q": [round(float(v), 1) for v in np.quantile(Ta[k], [0.1, 0.5, 0.9])] if anim[k].any() else None}
                 for g, k in groups.items()}
deep = cls[idx] >= 2
per = {}
for m, tg in itertools.product(MODELS, ("D", "DH")):
    walk, ref = solve(m, tg); per[(m, tg)] = (walk, ref)
def fails(T, walk, dep):
    return (T - dep - walk) < 0
rows = []
for m, tg, dep in itertools.product(MODELS, ("D", "DH"), (5, 10, 15)):
    walk, ref = per[(m, tg)]
    r = {"model": m, "refuges": tg, "depart": dep}
    for g, k in groups.items():
        if g.endswith("_anim"):
            f = fails(Ta, walk, dep) & k
            r[g] = [round(float(pop[idx][f].sum())), round(float(p65[idx][f].sum())), round(float(pop[idx][f & deep].sum()))]
        else:
            f6 = fails(np.full(len(idx), 6.0), walk, dep) & k; f10 = fails(np.full(len(idx), 10.0), walk, dep) & k
            r[g] = [[round(float(pop[idx][f10].sum())), round(float(pop[idx][f6].sum()))], [round(float(p65[idx][f10].sum())), round(float(p65[idx][f6].sum()))]]
    # city timing sensitivity (Shingū, animation area): T capped at 15 min
    Tc = np.minimum(Ta, 15.0); f = fails(Tc, walk, dep) & groups["Shingu_anim"]
    r["Shingu_anim_cityTiming15"] = [round(float(pop[idx][f].sum())), round(float(p65[idx][f].sum()))]
    rows.append(r)
out["scenarios"] = rows
# the city's difficult area 王子・熊野地 (H25: 185 people, 7–15 min): our counts in 王子町 and 熊野地 small areas
dist_mask = np.array([n.startswith("王子町") or n.startswith("熊野地") for n in sa_name])
walk, ref = per[("W", "DH")]
out["ouji_kumanoji"] = {"people_in_2026_max": round(float(pop[idx][dist_mask].sum())), "arrival_q": [round(float(v), 1) for v in np.quantile(Ta[dist_mask & anim], [0.1, 0.5, 0.9])],
                        "fail_W_DH_5": round(float(pop[idx][dist_mask & fails(Ta, walk, 5)].sum())),
                        "fail_W_DH_5_cityTiming15": round(float(pop[idx][dist_mask & fails(np.minimum(Ta, 15.0), walk, 5)].sum())),
                        "fail_W_DH_5_cityTiming7": round(float(pop[idx][dist_mask & fails(np.minimum(Ta, 7.0), walk, 5)].sum())),
                        "fail_W_DH_10": round(float(pop[idx][dist_mask & fails(Ta, walk, 10)].sum()))}
# latest safe departure (W, DH): T − walk
lsd = Ta - walk
k = groups["Kiho_anim"]
out["kiho_latest_departure_q"] = [round(float(v), 1) for v in np.quantile(lsd[k], [0.1, 0.25, 0.5, 0.75, 0.9])]
out["kiho_people_latest_departure_below"] = {t: round(float(pop[idx][k & (lsd < t)].sum())) for t in (3, 5, 10)}
k = groups["Shingu_anim"]
out["shingu_latest_departure_q"] = [round(float(v), 1) for v in np.quantile(lsd[k], [0.1, 0.25, 0.5, 0.75, 0.9])]
# loads per refuge (W, DH, everyone in the 2026 maximum inundation goes to the refuge nearest in time)
load = collections.Counter(); load65 = collections.Counter()
for i, r_ in enumerate(ref):
    key = S[r_]["name"] if 0 <= r_ < len(S) else ("high ground" if r_ == len(S) else "none")
    load[key] += pop[idx][i]; load65[key] += p65[idx][i]
out["load_W_DH"] = {k_: round(v) for k_, v in load.most_common(15)}
# named places: arrival at the place, the walk from it to the first refuge (city rule, W; and 1 m/s, F), what is left
PLACES = {"Shingu_station": (135.9941, 33.7251), "Shingu_cityhall": (135.992493, 33.724121), "Hayatama": (135.9837, 33.7323),
          "Udono_station": (136.0156, 33.73661), "Kiho_townhall": (136.00973, 33.73384)}
out["places"] = {}
for k, (lo, la) in PLACES.items():
    px, py = hz.TR(lo, la); pm = hz.muni_of(np.array([px]), np.array([py]))
    Tp = hz.arrival("kyodai", np.array([px]), np.array([py]))[0][0]
    d0, n0 = tree.query(np.array([[px, py]])); d0, n0 = float(d0[0]), int(n0[0])
    r = {"cls_max": int(hz.tsunami_max(np.array([px]), np.array([py]), pm)[0]), "arrival_min": None if np.isnan(Tp) else round(float(Tp), 1)}
    for m in ("W", "F"):
        wk = (d0 / MODELS[m][2] + DIST[(m, "DH")][n0]) / 60.0
        r[f"walk_{m}"] = round(float(wk), 1); r[f"left_{m}_5"] = None if np.isnan(Tp) else round(float(Tp - 5 - wk), 1)
    out["places"][k] = r
json.dump(out, open("evac_summary.json", "w"), ensure_ascii=False, indent=1)
print("places", json.dumps(out["places"], ensure_ascii=False))
np.savez_compressed("evac.npz", idx=idx, Ta=Ta, anim=anim, cls=cls[idx], walk_W_DH=per[("W", "DH")][0], walk_C_DH=per[("C", "DH")][0],
                    walk_F_DH=per[("F", "DH")][0], walk_E_DH=per[("E", "DH")][0], walk_W_D=per[("W", "D")][0], ref_W_DH=per[("W", "DH")][1])
print(json.dumps({k_: out[k_] for k_ in ("n_buildings", "people", "p65", "groups", "ouji_kumanoji", "kiho_latest_departure_q", "kiho_people_latest_departure_below", "shingu_latest_departure_q", "load_W_DH")}, ensure_ascii=False, indent=1))
for r in rows:
    if r["refuges"] == "DH": print(r)
