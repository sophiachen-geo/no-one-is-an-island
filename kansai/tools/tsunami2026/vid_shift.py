"""Last step of the animation's registration: the shift (in steps of half a panel pixel, up to 2 px) that best overlays the
animation's ever-wet land on the digitised R8 maximum-class map inside Shingū (intersection over union). The photographs
place the panel to about a pixel; the inundation itself decides the rest.
usage: vid_shift.py <decoded.npz> <affine.npy> <r8_k_grid.npz> <out_affine.npy>"""
import sys, json, numpy as np
Z = np.load(sys.argv[1]); A = np.load(sys.argv[2]); G = np.load(sys.argv[3])
first = Z["first"]; w0 = Z["water0"]; grid = G["grid"]; cov = G["cov"]; city = G["city"]; e0 = float(G["e0"]); n1 = float(G["n1"])
h, w = first.shape; yy, xx = np.mgrid[0:h, 0:w]; subs = np.linspace(-0.4, 0.4, 5)
def sample(arr, dxs=0.0, dys=0.0):
    acc = np.zeros((h, w)); cnt = np.zeros((h, w))
    for dy in subs:
        for dx in subs:
            x = xx + 0.5 + dx + dxs; y = yy + 0.5 + dy + dys
            E = A[0] * x + A[1] * y + A[2]; N = A[3] * x + A[4] * y + A[5]
            c = np.floor(E - e0).astype(int); r = np.floor(n1 - N).astype(int)
            ok = (r >= 0) & (r < arr.shape[0]) & (c >= 0) & (c < arr.shape[1])
            v = np.zeros((h, w)); v[ok] = arr[r[ok], c[ok]]; acc += v; cnt += ok
    return acc / np.maximum(cnt, 1)
S_ = (sample(city.astype(np.uint8)) >= 0.99) & (sample(cov.astype(np.uint8)) >= 0.99)
land = ~w0; vw = land & (first >= 0)
best = None
for sy in np.arange(-2, 2.01, 0.5):
    for sx in np.arange(-2, 2.01, 0.5):
        mp = sample((grid > 0).astype(np.uint8), sx, sy) >= 0.5
        iou = (vw & mp & S_).sum() / ((vw | mp) & land & S_).sum()
        if best is None or iou > best[0]: best = (float(iou), float(sx), float(sy))
iou0 = None
mp0 = sample((grid > 0).astype(np.uint8)) >= 0.5
iou0 = float((vw & mp0 & S_).sum() / ((vw | mp0) & land & S_).sum())
_, sx, sy = best
A2 = A.copy(); A2[2] = A[2] + A[0] * sx + A[1] * sy; A2[5] = A[5] + A[3] * sx + A[4] * sy
np.save(sys.argv[4], A2)
mp = sample((grid > 0).astype(np.uint8), sx, sy) >= 0.5
b = (vw & mp & S_).sum()
print(json.dumps({"iou_before": round(iou0, 3), "iou_after": round(best[0], 3), "shift_px": [sx, sy],
                  "precision": round(float(b / (vw & S_).sum()), 3), "recall": round(float(b / (mp & land & S_).sum()), 3)}))
