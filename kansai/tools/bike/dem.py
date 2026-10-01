"""On-demand GSI DEM sampling for route profiles.
Sources (GSI 標高タイル, PNG): dem5a (laser, z15) > dem5b (photogrammetry, z15) > dem5c (z15) > dem (DEM10B, z14).
h = (R*2^16 + G*2^8 + B) * 0.01 m; (128,0,0) = no data. Bilinear sampling inside the tile pixel grid.
Tiles are cached in ./dem_tiles/ so every run is reproducible offline."""
import math, os, io, time, urllib.request, numpy as np
from PIL import Image
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dem_tiles")
os.makedirs(CACHE, exist_ok=True)
LAYERS = [("dem5a_png", 15), ("dem5b_png", 15), ("dem5c_png", 15), ("dem_png", 14)]
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
_mem = {}
def _fetch(layer, z, tx, ty):
    key = (layer, z, tx, ty)
    if key in _mem:
        return _mem[key]
    f = os.path.join(CACHE, f"{layer}_{z}_{tx}_{ty}.png")
    if not os.path.exists(f) and not os.path.exists(f + ".404"):
        for a in range(5):
            try:
                data = urllib.request.urlopen(urllib.request.Request(
                    f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{tx}/{ty}.png", headers=UA), timeout=60).read()
                open(f, "wb").write(data); break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    open(f + ".404", "w").close(); break
                time.sleep(2 * (a + 1))
            except Exception:
                time.sleep(2 * (a + 1))
    if not os.path.exists(f):
        _mem[key] = None; return None
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.int64)
    v = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
    h = np.where(v < 2 ** 23, v, v - 2 ** 24).astype(np.float64) * 0.01
    h[(a[..., 0] == 128) & (a[..., 1] == 0) & (a[..., 2] == 0)] = np.nan
    _mem[key] = h
    return h
def _px(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n * 256
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * 256
    return x, y
def _bilinear(layer, z, lon, lat):
    x, y = _px(lon, lat, z)
    x -= 0.5; y -= 0.5                      # pixel centres
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    vals = []
    for dy in (0, 1):
        for dx in (0, 1):
            X, Y = x0 + dx, y0 + dy
            t = _fetch(layer, z, X // 256, Y // 256)
            if t is None: return None
            v = t[Y % 256, X % 256]
            if np.isnan(v): return None
            vals.append(v)
    return (vals[0] * (1 - fx) * (1 - fy) + vals[1] * fx * (1 - fy) + vals[2] * (1 - fx) * fy + vals[3] * fx * fy)
def sample(lon, lat):
    """Return (height_m, layer) from the finest layer with data at this point."""
    for layer, z in LAYERS:
        h = _bilinear(layer, z, lon, lat)
        if h is not None:
            return h, layer
    return None, None
