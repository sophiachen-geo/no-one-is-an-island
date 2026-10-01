"""GSI seamless aerial photographs (seamlessphoto, z15) over 135.94–136.04 E × 33.67–33.77 N -> ./photo15 (cached). Used only
to find where the animation's map panel lies (vid_register.py); nothing of them is kept, drawn or published."""
import math, os, subprocess, concurrent.futures as cf
z = 15
def tile(lon, lat):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
x0, y0 = tile(135.94, 33.77); x1, y1 = tile(136.04, 33.67)
os.makedirs("photo15", exist_ok=True)
def get(xy):
    x, y = xy; fn = f"photo15/{z}_{x}_{y}.jpg"
    if os.path.exists(fn) and os.path.getsize(fn) > 0: return 0
    return subprocess.run(["curl", "-sS", "-f", "-o", fn, f"https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"], capture_output=True).returncode
jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
with cf.ThreadPoolExecutor(8) as ex: rc = list(ex.map(get, jobs))
print(len(jobs), "tiles;", sum(1 for r in rc if r), "missing (open sea)")
