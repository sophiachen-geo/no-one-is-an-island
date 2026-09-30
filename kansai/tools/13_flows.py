"""Ordered flow lines for the hinterland map: timber/charcoal down the Kitayama and Kumano rivers to
Shingu, then schematic sea lanes toward Osaka and Edo. Writes flows.json (lon/lat)."""
import json
from shapely.geometry import LineString, Point, mapping
from shapely.ops import linemerge, unary_union, substring, transform
from pyproj import Transformer
TF = Transformer.from_crs(4326, 6674, always_xy=True).transform
INV = Transformer.from_crs(6674, 4326, always_xy=True).transform
rv = json.load(open("osm/rivers.json"))["elements"]
def merged(name):
    ls = [transform(TF, LineString([(p["lon"], p["lat"]) for p in e["geometry"]])) for e in rv
          if e["type"] == "way" and e.get("tags", {}).get("name") == name and len(e.get("geometry", [])) > 1]
    return linemerge(unary_union(ls))
def between(line, a_ll, b_ll):
    parts = list(getattr(line, "geoms", [line]))
    A = Point(*TF(*a_ll)); B = Point(*TF(*b_ll))
    best = min(parts, key=lambda p: p.distance(A) + p.distance(B))
    ta, tb = best.project(A), best.project(B)
    seg = substring(best, ta, tb)            # substring reverses when ta > tb, keeping A -> B order
    return seg
out = {}
kit = merged("北山川")
out["flow_kitayama"] = between(kit, (135.975, 33.935), (135.905, 33.792))       # Kitayama village -> Miyai confluence
kum = merged("熊野川")
parts = list(getattr(kum, "geoms", [kum]))
up = max(parts, key=lambda p: p.length)
low = min((p for p in parts if p is not up), key=lambda p: p.length * 0 + p.distance(Point(up.coords[-1])))
main = LineString(list(up.coords) + list(low.coords))
out["flow_kumano"] = between(main, (135.793, 33.990), (136.014, 33.725))        # Totsukawa -> mouth
# schematic sea lanes from the mouth (Ikeda) : south-west round Cape Shiono toward Osaka; north-east toward Edo
osaka = [(136.012, 33.722), (136.03, 33.66), (135.99, 33.56), (135.86, 33.45), (135.74, 33.40), (135.55, 33.45), (135.38, 33.58), (135.27, 33.66)]
edo = [(136.012, 33.722), (136.07, 33.78), (136.16, 33.86), (136.26, 33.96), (136.36, 34.05), (136.41, 34.12)]
out["sea_osaka"] = transform(TF, LineString(osaka)); out["sea_edo"] = transform(TF, LineString(edo))
for k, g in out.items(): print(k, round(g.length / 1000, 1), "km")
json.dump({k: mapping(transform(INV, g.simplify(40))) for k, g in out.items()}, open("flows.json", "w"))
