"""Town core (Shingū): GSI optimal vector tiles z16 (RdCL road centre lines with vt_rdctg / vt_rnkwidth, RdEdg road
edges, WA water areas, WL water lines, BldA buildings) and OSM POIs (shops, amenities, worship, parking, water)."""
import os, json, math, time, urllib.request, urllib.parse, sys
TB = (135.972, 33.712, 136.004, 33.736)
D = os.path.join(os.getcwd(), "town")
UA = {"User-Agent": "no-one-is-an-island kansai research (github sophiachen-geo)"}
def tile(lon, lat, z=16):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
(x0, y0), (x1, y1) = tile(TB[0], TB[3]), tile(TB[2], TB[1])
os.makedirs(os.path.join(D, "obv16"), exist_ok=True)
n = 0
for tx in range(x0, x1 + 1):
    for ty in range(y0, y1 + 1):
        f = os.path.join(D, "obv16", f"16_{tx}_{ty}.pbf")
        if os.path.exists(f): continue
        for a in range(5):
            try:
                b = urllib.request.urlopen(urllib.request.Request(f"https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/16/{tx}/{ty}.pbf", headers=UA), timeout=60).read()
                open(f, "wb").write(b); n += 1; break
            except urllib.error.HTTPError as e:
                if e.code == 404: open(f, "wb").close(); break
                time.sleep(2 + 2 * a)
            except Exception:
                time.sleep(2 + 2 * a)
print("tiles", (x1 - x0 + 1) * (y1 - y0 + 1), "new", n, file=sys.stderr)
Q = f'[out:json][timeout:120];(nwr["shop"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["amenity"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["tourism"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["landuse"="religious"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["natural"~"^(water|wood|tree_row|tree)$"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["leisure"="park"]({TB[1]},{TB[0]},{TB[3]},{TB[2]});nwr["historic"]({TB[1]},{TB[0]},{TB[3]},{TB[2]}););out body geom qt;'
for a in range(6):
    try:
        req = urllib.request.Request("https://maps.mail.ru/osm/tools/overpass/api/interpreter", data=urllib.parse.urlencode({"data": Q}).encode(), headers=UA)
        d = json.loads(urllib.request.urlopen(req, timeout=180).read())
        json.dump(d, open(os.path.join(D, "osm_pois.json"), "w")); print("pois", len(d["elements"]), d["osm3s"]["timestamp_osm_base"], file=sys.stderr); break
    except Exception as e:
        print("retry", a, repr(e)[:120], file=sys.stderr); time.sleep(10 + 10 * a)
