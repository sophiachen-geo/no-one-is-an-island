"""Municipal / prefectural polygons from MLIT N03 (2026-01-01); basin shares by prefecture and municipality;
the Higashimuro region. Writes munis.geojson, prefs.geojson, higashimuro.geojson."""
import json
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform
from pyproj import Transformer
tf = Transformer.from_crs(6668, 6674, always_xy=True).transform
munis = {}
for pc in ("30", "24", "29"):
    d = json.load(open(f"ksj/N03-20260101_{pc}.geojson", encoding="utf-8"))
    for ft in d["features"]:
        p = ft["properties"]; name = p["N03_004"]; code = p["N03_007"]
        if name == "所属未定地": continue
        munis.setdefault((p["N03_001"], name, code), []).append(shape(ft["geometry"]).buffer(0))
M = {k: unary_union(v) for k, v in munis.items()}
json.dump({f"{k[0]}|{k[1]}|{k[2]}": mapping(v) for k, v in M.items()}, open("munis.geojson", "w"))
pref = {}
for (pn, name, code), g in M.items(): pref.setdefault(pn, []).append(g)
P = {k: unary_union(v) for k, v in pref.items()}
json.dump({k: mapping(v) for k, v in P.items()}, open("prefs.geojson", "w"))
basin = shape(json.load(open("basin.geojson")))
bp = transform(tf, basin)
print("basin area km2 (EPSG:6674)", round(bp.area / 1e6, 1))
tot = 0
for k, g in P.items():
    a = bp.intersection(transform(tf, g)).area / 1e6; tot += a
    print("pref", k, round(a, 1), f"{100*a/(bp.area/1e6):.1f}%")
print("sum", round(tot, 1))
rows = []
for (pn, name, code), g in M.items():
    gp = transform(tf, g)
    a = bp.intersection(gp).area / 1e6
    if a > 0.5: rows.append((a, pn, name, code, gp.area / 1e6))
for a, pn, name, code, ma in sorted(rows, reverse=True):
    print(f"{pn} {name} {code}: {a:.1f} km2 in basin = {100*a/(bp.area/1e6):.1f}% of basin; {100*a/ma:.0f}% of municipality ({ma:.0f} km2)")
hig = ["新宮市", "那智勝浦町", "太地町", "古座川町", "北山村", "串本町"]
H = unary_union([g for (pn, n, c), g in M.items() if pn == "和歌山県" and n in hig])
Hp = transform(tf, H)
print("Higashimuro area km2", round(Hp.area / 1e6, 1), "basin share inside Higashimuro", f"{100*bp.intersection(Hp).area/bp.area:.1f}%")
json.dump(mapping(H), open("higashimuro.geojson", "w"))
