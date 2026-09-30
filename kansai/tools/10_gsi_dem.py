"""Download GSI DEM5A (5 m, laser) PNG tiles for the Shingu urban window and mosaic into a float grid.
GSI elevation PNG: h = (R*2^16 + G*2^8 + B) * 0.01 m, with (128,0,0) = no data."""
import math, os, io, urllib.request, numpy as np, json
from PIL import Image
Z = 15
W_, S_, E_, N_ = 135.93, 33.66, 136.05, 33.77      # urban core + Kiho + Miwasaki
def tile(lon, lat):
    n = 2 ** Z; x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y
x0, y0 = tile(W_, N_); x1, y1 = tile(E_, S_)
tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
os.makedirs("gsi", exist_ok=True)
H = (ty1 - ty0 + 1) * 256; Wd = (tx1 - tx0 + 1) * 256
grid = np.full((H, Wd), np.nan, dtype=np.float32)
for ty in range(ty0, ty1 + 1):
    for tx in range(tx0, tx1 + 1):
        f = f"gsi/dem5a_{Z}_{tx}_{ty}.png"
        if not os.path.exists(f):
            try:
                data = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/{Z}/{tx}/{ty}.png", headers={"User-Agent": "kansai-map-research"}), timeout=60).read()
                open(f, "wb").write(data)
            except Exception as e:
                print("missing", tx, ty, e); continue
        a = np.asarray(Image.open(f).convert("RGB")).astype(np.int64)
        v = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
        h = np.where(v < 2 ** 23, v, v - 2 ** 24).astype(np.float64) * 0.01
        h[(a[..., 0] == 128) & (a[..., 1] == 0) & (a[..., 2] == 0)] = np.nan
        grid[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = h
np.save("gsi_dem5.npy", grid)
json.dump({"z": Z, "tx0": tx0, "ty0": ty0, "H": H, "W": Wd}, open("gsi_dem5.json", "w"))
print("grid", grid.shape, "nan share", float(np.isnan(grid).mean()), "range", float(np.nanmin(grid)), float(np.nanmax(grid)))
