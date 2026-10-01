"""Kamikura mountain-foot micro-study: raw data for the study frame and the transect.

Run from the work directory (e.g. <work>/kmk). Writes
  dem1/   GSI DEM1A (1 m, airborne laser) elevation tiles, z17   → dem1.npy + dem1.json (tile origin, size)
  osm.json  every OSM feature in the frame (Overpass), © OpenStreetMap contributors, ODbL

GSI elevation PNG: h = (R·2^16 + G·2^8 + B) · 0.01 m (two's complement above 2^23); (128,0,0) = no data.
"""
import json, math, os, sys, urllib.request, urllib.parse, io, time
import numpy as np
from PIL import Image

W_, S_, E_, N_ = 135.9760, 33.7165, 135.9990, 33.7315       # study frame + transect to central Shingū
Z = 17                                                       # DEM1A native ≈ 1 m at this zoom (0.99 m at 33.7°)
UA = {"User-Agent": "no-one-is-an-island kansai research (kamikura micro-study)"}


def tile(lon, lat, z):
    n = 2 ** z; r = math.radians(lat)
    return (lon + 180) / 360 * n, (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n


def fetch_dem():
    os.makedirs("dem1", exist_ok=True)
    x0, y0 = tile(W_, N_, Z); x1, y1 = tile(E_, S_, Z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    H, Wd = (ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256
    grid = np.full((H, Wd), np.nan, dtype=np.float32)
    src = np.zeros((H, Wd), dtype=np.uint8)                  # 1 = DEM1A, 5 = DEM5A fallback
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            for name, z in (("dem1a_png", Z), ("dem5a_png", 15)):
                f = f"dem1/{name}_{z}_{tx}_{ty}.png"
                if name == "dem5a_png":                     # 5 m fallback: read the z15 parent and upsample ×4
                    px, py = tx >> 2, ty >> 2
                    f = f"dem1/{name}_15_{px}_{py}.png"
                    url = f"https://cyberjapandata.gsi.go.jp/xyz/{name}/15/{px}/{py}.png"
                else:
                    url = f"https://cyberjapandata.gsi.go.jp/xyz/{name}/{z}/{tx}/{ty}.png"
                if not os.path.exists(f):
                    try:
                        open(f, "wb").write(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
                    except urllib.error.HTTPError as e:
                        if e.code == 404: open(f, "wb").close()
                        else: raise
                if os.path.getsize(f) == 0:
                    continue
                a = np.asarray(Image.open(f).convert("RGB")).astype(np.int64)
                v = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
                h = np.where(v < 2 ** 23, v, v - 2 ** 24).astype(np.float64) * 0.01
                h[(a[..., 0] == 128) & (a[..., 1] == 0) & (a[..., 2] == 0)] = np.nan
                if name == "dem5a_png":
                    ox, oy = (tx & 3) * 64, (ty & 3) * 64
                    h = np.kron(h[oy:oy + 64, ox:ox + 64], np.ones((4, 4)))
                sl = (slice((ty - ty0) * 256, (ty - ty0 + 1) * 256), slice((tx - tx0) * 256, (tx - tx0 + 1) * 256))
                cur = grid[sl]; fill = np.isnan(cur) & ~np.isnan(h)
                cur[fill] = h[fill]; src[sl][fill] = 1 if name == "dem1a_png" else 5
                if not np.isnan(cur).any():
                    break
    np.save("dem1.npy", grid); np.save("dem1_src.npy", src)
    json.dump({"z": Z, "tx0": tx0, "ty0": ty0, "H": H, "W": Wd, "bbox": [W_, S_, E_, N_]}, open("dem1.json", "w"))
    print("DEM grid", grid.shape, "1 m share %.3f" % (src == 1).mean(), "5 m fallback %.3f" % (src == 5).mean(),
          "no data %.4f" % np.isnan(grid).mean(), "range %.2f–%.2f m" % (np.nanmin(grid), np.nanmax(grid)))


def fetch_osm():
    if os.path.exists("osm.json") and os.path.getsize("osm.json") > 0:
        print("osm cached"); return
    bb = f"{S_},{W_},{N_},{E_}"
    q = f"""[out:json][timeout:240];
(
  way["highway"]({bb}); way["waterway"]({bb}); way["natural"]({bb}); relation["natural"]({bb});
  way["landuse"]({bb}); relation["landuse"]({bb}); way["leisure"]({bb}); way["amenity"]({bb}); relation["amenity"]({bb});
  way["building"]({bb}); relation["building"]({bb}); way["barrier"]({bb}); way["man_made"]({bb}); way["historic"]({bb});
  way["tourism"]({bb}); way["railway"]({bb}); way["bridge"]({bb}); way["place"]({bb});
  node["name"]({bb}); node["amenity"]({bb}); node["historic"]({bb}); node["natural"]({bb}); node["tourism"]({bb}); node["barrier"]({bb});
);
out geom tags;"""
    for ep in ("https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter"):
        for i in range(3):
            try:
                raw = urllib.request.urlopen(urllib.request.Request(ep, data=urllib.parse.urlencode({"data": q}).encode(), headers=UA), timeout=300).read()
                js = json.loads(raw)
                open("osm.json", "wb").write(raw)
                print("OSM", len(js["elements"]), "elements from", ep, "· base", js.get("osm3s", {}).get("timestamp_osm_base"))
                return
            except Exception as e:
                print("overpass", ep, i, e, file=sys.stderr); time.sleep(8 * (i + 1))
    raise SystemExit("overpass failed")


if __name__ == "__main__":
    fetch_dem()
    fetch_osm()
