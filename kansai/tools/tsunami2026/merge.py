"""Merge the two sheets of each Wakayama scenario onto one 1 m grid (EPSG:6674; a pixel takes the higher class where
the sheets overlap) and mark Shingū (N03, 1 January 2026). Reports the inundated area inside the city per class.
usage: merge.py <N03-20260101_30.geojson>   (reads cls_k1, cls_k2, cls_s1, cls_s2 .npz; writes r8_k_grid.npz, r8_s_grid.npz)"""
import json, numpy as np, sys
from shapely.geometry import shape
from shapely.ops import unary_union, transform as tf
from pyproj import Transformer
import rasterio.features, affine
tr = Transformer.from_crs(4326, 6674, always_xy=True).transform
N03 = json.load(open(sys.argv[1], encoding="utf-8"))
shingu = unary_union([shape(f["geometry"]) for f in N03["features"] if f["properties"].get("N03_004") == "新宮市"])
shingu = tf(tr, shingu)
res = {}
for scen, sheets in (("k", ("k1", "k2")), ("s", ("s1", "s2"))):
    G = [np.load(f"cls_{s}.npz") for s in sheets]
    e0 = min(float(g["e0"]) for g in G); n1 = max(float(g["n1"]) for g in G)
    e1 = max(float(g["e0"]) + g["grid"].shape[1] for g in G); n0 = min(float(g["n1"]) - g["grid"].shape[0] for g in G)
    W = int(round(e1 - e0)); H = int(round(n1 - n0))
    out = np.zeros((H, W), np.uint8); cov = np.zeros((H, W), bool)
    for g in G:
        r = int(round(n1 - float(g["n1"]))); c = int(round(float(g["e0"]) - e0)); h, w = g["grid"].shape
        out[r:r + h, c:c + w] = np.maximum(out[r:r + h, c:c + w], g["grid"]); cov[r:r + h, c:c + w] |= g["inside"]
    T = affine.Affine(1.0, 0, e0, 0, -1.0, n1)
    city = rasterio.features.rasterize([(shingu, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8").astype(bool)
    inc = out * city
    area = {int(j): int((inc == j).sum()) for j in range(1, 8)}
    tot = sum(area.values())
    res[scen] = {"inundated_ha_in_shingu": round(tot / 1e4, 1), "outside_city_ha": round(int(((out > 0) & ~city).sum()) / 1e4, 1), "class_ha": {k: round(v / 1e4, 1) for k, v in area.items()}}
    np.savez_compressed(f"r8_{scen}_grid.npz", grid=out, cov=cov, city=city, e0=e0, n1=n1)
print(json.dumps(res, ensure_ascii=False))
