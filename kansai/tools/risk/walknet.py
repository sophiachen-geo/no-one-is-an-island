"""Walking network: GSI 電子国土基本情報 road centre lines (optimal_bvmap-v1 z16 RdCL; every public road, lanes under
3 m included; expressways left out) joined at shared vertices, plus OpenStreetMap ways usable on foot (2026-10-01; brings
footpaths, steps and lanes GSI lacks), each OSM vertex tied to the nearest GSI vertex within 8 m.
In the three test areas OSM alone missed 13–34 % of GSI road length. Writes walknet.npz: vertex x, y, z (ground height); edge u, v, length, rise, steps, bridge, source (0 GSI, 1 OSM, 2 tie)."""
import json, sys, os, numpy as np
from scipy.spatial import cKDTree
import hz
import cfg
sys.path.insert(0, cfg.BIKE); import town_gsi; town_gsi.D = os.path.abspath("obv16")
X = []; Y = []; key = {}
U = []; V = []; ST = []; BR = []; SRC = []
def nid(x, y):
    k = (round(x * 2), round(y * 2))                    # 0.5 m snapping
    if k not in key: key[k] = len(X); X.append(x); Y.append(y)
    return key[k]
# vector tiles carry a buffer beyond their edges: clip every line to its own tile so neighbouring parts meet at the edge
import glob, mapbox_vector_tile
from shapely.geometry import LineString as _LS, box as _box
for f in sorted(glob.glob(os.path.join(town_gsi.D, "16_*.pbf"))):
    if not os.path.getsize(f): continue
    _, tx, ty = os.path.basename(f)[:-4].split("_"); tx, ty = int(tx), int(ty)
    t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
    Lr = t.get("RdCL")
    if not Lr: continue
    ext = Lr["extent"]; tb = _box(0, 0, ext, ext)
    for ft in Lr["features"]:
        p = ft["properties"]
        if p.get("vt_motorway") == 1: continue
        gg = ft["geometry"]; cs = gg["coordinates"]
        parts = [cs] if gg["type"] == "LineString" else (cs if gg["type"] == "MultiLineString" else [])
        for part in parts:
            if len(part) < 2: continue
            cl = _LS(part).intersection(tb)
            for seg in (cl.geoms if hasattr(cl, "geoms") else [cl]):
                if seg.is_empty or seg.geom_type != "LineString": continue
                ids = [nid(*hz.TR(*town_gsi._ll(tx, ty, ext, x, y))) for x, y in seg.coords]
                for a, b in zip(ids, ids[1:]):
                    if a != b: U.append(a); V.append(b); ST.append(False); BR.append(p.get("vt_lvorder", 0) > 0); SRC.append(0)
ngsi = len(X)
d = json.load(open(cfg.ROADS))
BB = (135.93, 33.66, 136.06, 33.80)
onodes = {}
for e in d["elements"]:
    if e.get("type") != "way" or not e.get("geometry"): continue
    t = e.get("tags", {})
    if t.get("highway") in ("motorway", "motorway_link"): continue
    if t.get("foot") in ("no", "private") or (t.get("access") in ("no", "private") and t.get("foot") not in ("yes", "designated", "permissive")): continue
    g = e["geometry"]; ns = e.get("nodes")
    if not ns or len(ns) != len(g): continue
    if not any(BB[0] <= q["lon"] <= BB[2] and BB[1] <= q["lat"] <= BB[3] for q in g): continue
    st = t.get("highway") == "steps"; br = t.get("bridge") not in (None, "no") or t.get("tunnel") not in (None, "no")
    ids = []
    for n, q in zip(ns, g):
        if n not in onodes:
            x, y = hz.TR(q["lon"], q["lat"]); onodes[n] = len(X); X.append(x); Y.append(y)
        ids.append(onodes[n])
    for a, b in zip(ids, ids[1:]):
        if a != b: U.append(a); V.append(b); ST.append(st); BR.append(br); SRC.append(1)
X = np.array(X); Y = np.array(Y)
# tie OSM vertices to GSI vertices within 8 m
tree = cKDTree(np.c_[X[:ngsi], Y[:ngsi]])
oi = np.arange(ngsi, len(X)); dd, nn_ = tree.query(np.c_[X[oi], Y[oi]])
k = dd <= 8.0
U += list(oi[k]); V += list(nn_[k]); ST += [False] * int(k.sum()); BR += [False] * int(k.sum()); SRC += [2] * int(k.sum())
U = np.array(U); V = np.array(V); ST = np.array(ST); BR = np.array(BR); SRC = np.array(SRC)
L = np.hypot(X[U] - X[V], Y[U] - Y[V])
print("GSI vertices", ngsi, "OSM vertices", len(X) - ngsi, "edges", len(U), "GSI km", round(L[SRC == 0].sum() / 1000, 1),
      "OSM km", round(L[SRC == 1].sum() / 1000, 1), "ties", int(k.sum()), file=sys.stderr)
Z = hz.ground(X, Y)
print("vertices without height", int(np.isnan(Z).sum()), file=sys.stderr)
rise = np.abs(Z[U] - Z[V]); rise[BR] = 0.0; rise[SRC == 2] = 0.0; rise = np.nan_to_num(rise)
np.savez_compressed("walknet.npz", x=X, y=Y, z=Z, u=U, v=V, length=L, rise=rise, steps=ST, bridge=BR, src=SRC, osm_base=d["osm3s"]["timestamp_osm_base"])
