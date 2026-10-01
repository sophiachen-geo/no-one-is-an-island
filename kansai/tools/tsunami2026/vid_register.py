"""Georeference the map panel of Wakayama's R8 Shingū animation to JGD2011 / CS VI (EPSG:6674).
Reference: GSI seamless aerial photographs (z15, used only to find the transform; nothing of them is kept or shown),
resampled to a 4 m grid in EPSG:6674. The animation's first frame (land only; water drawn by the animation masked)
is matched on gradient magnitude: a scan over scale with FFT cross-correlation, then a 6-parameter affine refined by
normalised cross-correlation (Powell).
usage: vid_register.py <decoded.npz> <out_affine.npy>   (photo tiles: PHOTO_DIR, default ./photo15, from fetch_photo.py)   (affine: E = a x + b y + c, N = d x + e y + f; x, y = panel px)"""
import sys, os, glob, math, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.optimize import minimize
from pyproj import Transformer
src, out = sys.argv[1:3]
D = os.environ.get("PHOTO_DIR", os.path.join(os.getcwd(), "photo15"))
z = 15; n = 2 ** z
tiles = {}
for f in glob.glob(D + "/15_*.jpg"):
    _, x, y = f.split("/")[-1][:-4].split("_"); tiles[(int(x), int(y))] = f
xs = [k[0] for k in tiles]; ys = [k[1] for k in tiles]
X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
mos = np.zeros(((Y1 - Y0 + 1) * 256, (X1 - X0 + 1) * 256), np.float32)
for (x, y), f in tiles.items():
    mos[(y - Y0) * 256:(y - Y0 + 1) * 256, (x - X0) * 256:(x - X0 + 1) * 256] = np.asarray(Image.open(f).convert("L"), np.float32)
# reference grid in EPSG:6674, 4 m
T = Transformer.from_crs(6674, 4326, always_xy=True)
TF = Transformer.from_crs(4326, 6674, always_xy=True)
e_min, n_min = TF.transform(135.945, 33.672); e_max, n_max = TF.transform(136.035, 33.765)
R = 4.0
E = np.arange(e_min, e_max, R); N = np.arange(n_max, n_min, -R)
EE, NN = np.meshgrid(E, N)
lon, lat = T.transform(EE, NN)
px = ((lon + 180) / 360 * n - X0) * 256
py = ((1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n - Y0) * 256
ref = ndi.map_coordinates(mos, [py, px], order=1, cval=0)
refok = ndi.map_coordinates((mos > 0).astype(np.float32), [py, px], order=0, cval=0) > 0
def grad(a):
    a = ndi.gaussian_filter(a, 1.0)
    return np.hypot(ndi.sobel(a, 0), ndi.sobel(a, 1))
G = grad(ref) * refok
Z = np.load(src); f0 = Z["frame0"].astype(np.float32).mean(2); w0 = Z["water0"]
land = ndi.binary_erosion(~w0, iterations=2)
g_v = grad(f0) * land
def ncc_fft(img, tpl, msk):
    # normalised cross-correlation of template tpl (with mask) over img, via FFT
    from numpy.fft import rfft2, irfft2
    H, W = img.shape; h, w = tpl.shape
    s = (H + h, W + w)
    t = (tpl - tpl[msk].mean()) * msk
    num = irfft2(rfft2(img, s) * np.conj(rfft2(t, s)), s)[:H, :W]
    m = msk.astype(float)
    s1 = irfft2(rfft2(img, s) * np.conj(rfft2(m, s)), s)[:H, :W]
    s2 = irfft2(rfft2(img * img, s) * np.conj(rfft2(m, s)), s)[:H, :W]
    k = m.sum(); var = s2 - s1 * s1 / k
    out = np.full((H, W), -1.0)
    ok = var > 0.05 * np.median(var[var > 0])
    out[ok] = num[ok] / np.sqrt(var[ok] * (t * t).sum())
    out[H - h + 1:, :] = -1; out[:, W - w + 1:] = -1          # template must lie inside the reference
    return out
best = None
for sc in np.arange(7.0, 13.01, 0.25):                      # metres per panel pixel
    zf = sc / R
    tpl = ndi.zoom(g_v, zf, order=1); msk = ndi.zoom(land.astype(float), zf, order=0) > 0.5
    if tpl.shape[0] >= G.shape[0] or tpl.shape[1] >= G.shape[1]: continue
    c = ncc_fft(G, tpl, msk)
    i = np.unravel_index(np.argmax(c), c.shape)
    if best is None or c[i] > best[0]: best = (float(c[i]), sc, i)
    print(round(sc, 2), round(float(c[i]), 4), i, file=sys.stderr)
score, sc, (r0, c0) = best
print("scan best", best, file=sys.stderr)
# panel px (x, y) -> E, N
a0 = np.array([sc, 0, E[0] + c0 * R, 0, -sc, N[0] - r0 * R])
yy, xx = np.nonzero(land)
sel = np.random.default_rng(0).choice(len(xx), min(60000, len(xx)), replace=False); xx = xx[sel].astype(float); yy = yy[sel].astype(float)
gv = g_v[yy.astype(int), xx.astype(int)]
def cost(p):
    e = p[0] * xx + p[1] * yy + p[2]; nn = p[3] * xx + p[4] * yy + p[5]
    r = (N[0] - nn) / R; c = (e - E[0]) / R
    gr = ndi.map_coordinates(G, [r, c], order=1, cval=0)
    a = gv - gv.mean(); b = gr - gr.mean()
    den = math.sqrt((a * a).sum() * (b * b).sum())
    return -float((a * b).sum() / den) if den > 0 else 0.0
s = np.array([0.01, 0.01, 5, 0.01, 0.01, 5])
r = minimize(lambda u: cost(a0 + u * s), np.zeros(6), method="Powell", options={"xtol": 1e-4, "ftol": 1e-7, "maxiter": 20000})
aff = a0 + r.x * s
np.save(out, aff)
sx = math.hypot(aff[0], aff[3]); sy = math.hypot(aff[1], aff[4])
print(json.dumps({"scan_scale_m": sc, "scan_ncc": round(score, 4), "ncc_start": round(-cost(a0), 4), "ncc_final": round(-r.fun, 4),
                  "m_per_px": [round(sx, 3), round(sy, 3)], "rot_deg": round(math.degrees(math.atan2(aff[3], aff[0])), 3),
                  "corner_ll": [T.transform(aff[2], aff[5]), T.transform(aff[0] * 686 + aff[1] * 542 + aff[2], aff[3] * 686 + aff[4] * 542 + aff[5])]}))
