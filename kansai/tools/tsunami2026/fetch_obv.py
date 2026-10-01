"""GSI optimal vector tiles (optimal_bvmap-v1, z16) over a lon/lat box -> ./obv16 (cached; empty file for a 404).
The registration used 135.94–136.035 E × 33.655–33.75 N (396 tiles, fetched 2026-10-01).
usage: fetch_obv.py <lon0> <lat0> <lon1> <lat1>"""
import os, sys, math, time, urllib.request
D = os.path.join(os.getcwd(), "obv16"); os.makedirs(D, exist_ok=True)
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
def tile(lon, lat, z=16):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
lo0, la0, lo1, la1 = map(float, sys.argv[1:5])
x0, y1 = tile(lo0, la0); x1, y0 = tile(lo1, la1)
n = got = 0
for tx in range(x0, x1 + 1):
    for ty in range(y0, y1 + 1):
        f = os.path.join(D, f"16_{tx}_{ty}.pbf"); n += 1
        if os.path.exists(f): continue
        for a in range(5):
            try:
                b = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/16/{tx}/{ty}.pbf", headers=UA), timeout=60).read()
                open(f, "wb").write(b); got += 1; break
            except urllib.error.HTTPError as e:
                if e.code == 404: open(f, "wb").close(); break
                time.sleep(2 + 2 * a)
            except Exception: time.sleep(2 + 2 * a)
print("tiles", n, "fetched", got)
