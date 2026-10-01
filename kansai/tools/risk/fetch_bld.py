"""GSI optimal vector tiles (optimal_bvmap-v1, z16: building outlines BldA, road centre lines RdCL) covering every 250 m census
cell with residents (derived_mesh250_2020_shingu_kiho.geojson from census.py) -> ./obv16 (cached; empty file for a 404).
Fetched for the page on 2026-10-01 (648 tiles)."""
import json, math, os, time, urllib.request, concurrent.futures as cf
os.makedirs("obv16", exist_ok=True)
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
cells = [f for f in json.load(open("derived_mesh250_2020_shingu_kiho.geojson", encoding="utf-8"))["features"] if (f["properties"].get("pop_total") or 0) > 0]
def tile(lon, lat, z=16):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
T = set()
for f in cells:
    cs = f["geometry"]["coordinates"][0]; xs = [c[0] for c in cs]; ys = [c[1] for c in cs]
    x0, y0 = tile(min(xs) + 1e-7, max(ys) - 1e-7); x1, y1 = tile(max(xs) - 1e-7, min(ys) + 1e-7)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1): T.add((x, y))
def get(t):
    tx, ty = t; f = f"obv16/16_{tx}_{ty}.pbf"
    if os.path.exists(f): return "cached"
    for a in range(5):
        try:
            b = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/16/{tx}/{ty}.pbf", headers=UA), timeout=60).read()
            open(f, "wb").write(b); return "fetched"
        except urllib.error.HTTPError as e:
            if e.code == 404: open(f, "wb").close(); return "404"
            time.sleep(2 + 2 * a)
        except Exception: time.sleep(2 + 2 * a)
    return "failed"
with cf.ThreadPoolExecutor(6) as ex: r = list(ex.map(get, sorted(T)))
import collections; print(len(T), "tiles", dict(collections.Counter(r)))
