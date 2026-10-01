"""Read Wakayama's R8 2D inundation animation frame by frame (1 frame = 10 s of simulated time; the clock printed on
frame n reads n×10 s) and record, per pixel of the map panel:
  first    first frame of 3 consecutive frames (30 s) drawn wet, where the pixel was not water at frame 0
  water0   drawn as water at frame 0 (sea, river, port; low ground drawn wet from the start by subsidence)
  maxlev   highest water level drawn (m, T.P.), read from the colour bar (−2.0 … 10.0 m, linear)
A pixel is drawn wet when its colour lies within 45 (RGB) of the colour bar and it has changed from frame 0 by more
than 40, or it was water at frame 0. Aerial-photo colours rarely come that close to the saturated bar.
usage: vid_decode.py <video.mp4> <out.npz>"""
import sys, subprocess, numpy as np, imageio_ffmpeg
src, out = sys.argv[1:3]
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
X0, Y0, X1, Y1 = 298, 69, 984, 611                       # map panel (inclusive-exclusive)
p = subprocess.Popen([FF, "-hide_banner", "-loglevel", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     stdout=subprocess.PIPE)
def frames():
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n: return
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
it = frames()
f0full = next(it)
bar = f0full[645, 658:908].astype(float)                 # 250 colours, −2.0 → 10.0 m
lev_of = np.linspace(-2.0, 10.0, len(bar))
# lookup table on a 6-bit RGB cube: nearest bar colour and its distance
q = np.arange(32) * 8 + 4
cube = np.stack(np.meshgrid(q, q, q, indexing="ij"), -1).reshape(-1, 3).astype(float)
d = np.linalg.norm(cube[:, None, :] - bar[None, :, :], axis=2)
LUT_d = d.min(1).reshape(32, 32, 32); LUT_i = d.argmin(1).reshape(32, 32, 32)
def classify(fr):
    a = fr[Y0:Y1, X0:X1]
    i = (a >> 3).astype(np.intp)
    dist = LUT_d[i[..., 0], i[..., 1], i[..., 2]]; idx = LUT_i[i[..., 0], i[..., 1], i[..., 2]]
    return a.astype(np.int16), dist, lev_of[idx]
a0, d0, l0 = classify(f0full)
water0 = (d0 < 45) & (l0 > -0.5) & (l0 < 2.5)            # tide level T.P.+1.0 m is drawn cyan
h, w = water0.shape
first = np.full((h, w), -1, np.int32); run = np.zeros((h, w), np.int16)
maxlev = np.full((h, w), np.nan, np.float32); wet_frames = np.zeros((h, w), np.int16)
n = 0
for fr in [f0full] + list(it):
    a, dd, ll = classify(fr)
    changed = np.abs(a - a0).sum(-1) > 40
    wet = (dd < 45) & (changed | water0)
    run = np.where(wet, run + 1, 0)
    new = (run == 3) & (first < 0)
    first[new] = n - 2
    wet_frames += wet
    m = wet & ~(ll <= np.nan_to_num(maxlev, nan=-9))
    maxlev[m] = ll[m]
    n += 1
p.wait()
np.savez_compressed(out, first=first, water0=water0, maxlev=maxlev, wet_frames=wet_frames, nframes=n, frame0=a0.astype(np.uint8))
land = ~water0
print({"frames": n, "panel": [h, w], "land_px": int(land.sum()), "land_ever_wet_px": int((land & (first >= 0)).sum()),
       "first_min_quantiles_land": [float(x) for x in np.quantile(first[land & (first >= 0)] * 10 / 60, [0, .1, .25, .5, .75, .9, 1])]})
