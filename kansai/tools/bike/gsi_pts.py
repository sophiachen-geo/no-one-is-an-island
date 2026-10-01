"""GSI optimal vector tiles (experimental_bvmap z16) along given lines: levelling benchmarks (7103),
triangulation points (7102) and spot heights (7201) with their heights. Tiles cached in ./bvmap/."""
import os, math, glob, time, urllib.request, mapbox_vector_tile
CACHE = os.path.join(os.getcwd(), "bvmap"); os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
Z = 16
def tile_of(lon, lat, z=Z):
    n = 2 ** z; x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)
def fetch(tx, ty):
    f = os.path.join(CACHE, f"16_{tx}_{ty}.pbf")
    if not os.path.exists(f):
        for a in range(5):
            try:
                b = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/16/{tx}/{ty}.pbf", headers=UA), timeout=60).read()
                open(f, "wb").write(b); break
            except urllib.error.HTTPError as e:
                if e.code == 404: open(f, "wb").close(); break
                time.sleep(2 + 2 * a)
            except Exception:
                time.sleep(2 + 2 * a)
    return f if os.path.exists(f) else None
KIND = {7102: "triangulation point", 7103: "levelling benchmark", 7201: "spot height"}
def points_in_tiles(tiles):
    out = []
    for tx, ty in tiles:
        f = fetch(tx, ty)
        if not f or not os.path.getsize(f): continue
        n = 2 ** Z
        t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
        for lname in ("symbol", "elevation"):
            L = t.get(lname)
            if not L: continue
            for ft in L["features"]:
                p = ft["properties"]; code = p.get("ftCode")
                if code not in KIND or "alti" not in p: continue
                cx, cy = ft["geometry"]["coordinates"]
                x = (tx + cx / L["extent"]) / n; y = (ty + cy / L["extent"]) / n
                out.append((round(x * 360 - 180, 7), round(math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y)))), 7), float(p["alti"]), KIND[code]))
    return sorted(set(out))
