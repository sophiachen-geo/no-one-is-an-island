"""Maintenance tool (network): re-verify named map points against OpenStreetMap via Nominatim.

    python3 kansai/qa/verify_points.py            # prints a report; writes nothing
    python3 kansai/qa/verify_points.py --toml     # also prints [points.*] blocks for points.toml

Not part of CI (Nominatim is rate-limited and live data drifts). Run it when points change,
review the distances, and copy the verified coordinates + OSM ids into points.toml.
"""
import json, re, sys, time, urllib.parse, urllib.request
from math import hypot
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tm  # noqa: E402

HTML = Path(__file__).resolve().parents[1] / "index.html"
UA = "no-one-is-an-island-qa/1.0 (github.com/sophiachen-geo/no-one-is-an-island)"
VIEWBOX = "135.1,34.6,136.6,33.3"  # Kii Peninsula; results outside are ignored

# key -> (query, preferred OSM categories)
QUERIES = {
    "shingu": ("新宮市役所", {"amenity", "office"}),
    "station": ("新宮駅", {"railway", "public_transport"}),
    "medical": ("新宮市立医療センター", {"amenity", "healthcare"}),
    "hayatama": ("熊野速玉大社", {"amenity"}),
    "kamikura": ("神倉神社", {"amenity"}),
    "hongu": ("熊野本宮大社", {"amenity"}),
    "hongu_office": ("本宮行政局", {"amenity", "office"}),
    "nachi": ("熊野那智大社", {"amenity"}),
    "miwasaki": ("三輪崎駅", {"railway", "public_transport"}),
    "kiho": ("紀宝町役場", {"amenity", "office"}),
    "kitayama": ("北山村役場", {"amenity", "office"}),
    "koguchi": ("小口 熊野川町", {"place", "boundary"}),
    "kumano": ("熊野市役所", {"amenity", "office"}),
    "owase": ("尾鷲市役所", {"amenity", "office"}),
    "totsukawa": ("十津川村役場", {"amenity", "office"}),
    "nachikatsuura": ("那智勝浦町役場", {"amenity", "office"}),
    "kushimoto": ("串本町役場", {"amenity", "office"}),
    "tanabe": ("田辺市役所", {"amenity", "office"}),
    "gojo": ("五條市役所", {"amenity", "office"}),
    "koyasan": ("金剛峯寺", {"amenity", "building", "historic"}),
    "yoshino": ("吉野町役場", {"amenity", "office"}),
    "dam_ikehara": ("池原ダム", {"waterway", "man_made"}),
    "dam_kazeya": ("風屋ダム", {"waterway", "man_made"}),
    "dam_futatsuno": ("二津野ダム", {"waterway", "man_made"}),
    "dam_nanairo": ("七色ダム", {"waterway", "man_made"}),
    "dam_komori": ("小森ダム", {"waterway", "man_made"}),
    "dam_saruya": ("猿谷ダム", {"waterway", "man_made"}),
    "dam_asahi": ("旭ダム", {"waterway", "man_made"}),
    "dam_seto": ("瀬戸ダム", {"waterway", "man_made"}),
}


def geo():
    s = HTML.read_text(encoding="utf-8")
    return json.loads(re.search(r"/\*GEO:BEGIN\*/(.*?)/\*GEO:END\*/", s, re.S).group(1))


def search(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": 8, "countrycodes": "jp", "viewbox": VIEWBOX, "bounded": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    g = geo(); out_toml = "--toml" in sys.argv
    for key, (q, cats) in QUERIES.items():
        try:
            res = search(q)
        except Exception as e:  # network trouble: report and continue
            print(f"{key:15s} ERROR {e}"); time.sleep(1.2); continue
        time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
        if not res:
            print(f"{key:15s} NOT FOUND ({q})"); continue
        best = sorted(res, key=lambda r: (r.get("category") not in cats, -float(r.get("importance") or 0)))[0]
        lon, lat = float(best["lon"]), float(best["lat"])
        px, py = g["pts"].get(key, [None, None])
        d = None if px is None else hypot(*(a - b for a, b in zip(tm.to_svg(lon, lat, g["origin"]), (px, py)))) * 100
        print(f"{key:15s} {best['name'][:18]:18s} {best['osm_type']} {best['osm_id']:<11} {lat:.5f},{lon:.5f}  "
              f"page offset {'—' if d is None else f'{d:6.0f} m'}  [{best.get('category')}/{best.get('type')}]")
        if out_toml:
            print(f'[points.{key}]\nname = "{best["name"]}"\nlon = {lon:.5f}\nlat = {lat:.5f}\n'
                  f'source = "OSM {best["osm_type"]} {best["osm_id"]} via Nominatim ({q})"\n')


if __name__ == "__main__":
    main()
