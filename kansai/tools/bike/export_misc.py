import json, os, re, sys, math
from pagegeo import pg, d_of, simp
from route import Graph, hav
H = os.getcwd(); R = os.environ.get("BIKE_RESEARCH", os.path.join(os.getcwd(), "..", "research", "bike"))
# ---- photographs (time-ordered; EXIF position and compass bearing) ----
CAP = {
 "IMG_5121.JPG": "阿須賀神社 (Asuka-jinja), the first stop: its hall below the wooded hill of 蓬莱山 (Hōraisan).",
 "IMG_5124.JPG": "Board of the Shingū City Board of Education (August 1992): 速玉大社のオガタマノキ, a city natural monument, 21 m tall with a girth of 1.65 m.",
 "IMG_5125.JPG": "The オガタマノキ (Michelia compressa) from below.",
 "IMG_5127.JPG": "Its trunk, beside one of the shrine’s buildings.",
 "IMG_5131.JPG": "Its roots at the foot of the building.",
 "IMG_5132.JPG": "熊野速玉大社 (Kumano Hayatama Taisha): the halls behind the shrine’s banner.",
 "IMG_5134.JPG": "One of the halls: offering box and bell rope.",
 "IMG_5137.JPG": "Green citrus fruit in the shrine grounds.",
 "IMG_5140.JPG": "A moss-covered stone monument in the grounds.",
 "IMG_5141.JPG": "The Nagi (梛) behind its fence, south-south-east of the shrine gate: “estimated to be 800 years old”, said to have been planted when the halls were rebuilt in 1159 (Agency for Cultural Affairs).",
 "IMG_5144.JPG": "Board: 熊野速玉大社参詣曼荼羅, the shrine’s pilgrimage mandala.",
 "IMG_5145.JPG": "Leaving along the approach, under the great torii, toward the town.",
 "IMG_5149.JPG": "At the foot of Kamikura: the board 「史跡 熊野三山（権現山）」 — Gongen-yama, its summit 千穂ヶ峰 (253 m), 神倉神社 on a cliff of nearly 100 m, and Gotobiki-iwa.",
 "IMG_5150.JPG": "Board: 天磐盾, dated 11 February 1990, for a stele set up in the 2,650th year of the imperial era; it cites the Nihon Shoki and names 高倉下命 and 八咫烏.",
 "IMG_5151.JPG": "Board: 神倉神社 — deities 高倉下命 and 天照大神; the Oto Matsuri on the night of 6 February.",
 "IMG_5157.JPG": "Youth Library えんがわ, a library in an old house at the foot of the mountain.",
 "IMG_5161.JPG": "Board of the Shingū City Board of Education: 妙心寺の由来 — the nunnery that was Kamikura’s 本願, the office that raised its funds; the role began with the nun 妙順尼’s collections for rebuilding Kamikura, from the Daiei years (1521–27) to 1531.",
 "IMG_5162.JPG": "神倉堀端都市下水路, the drainage channel at the foot of Kamikura-yama, looking north-west.",
 "IMG_5163.JPG": "A gourd vine trained over a garden wall beside the channel.",
 "IMG_5167.JPG": "The lane along the channel, the mountain on the right.",
 "IMG_5168.JPG": "Crabs at the waterline of the channel wall.",
 "IMG_5173.JPG": "Across the channel from the shrine’s lower precinct: the grounds of the 出雲大社新宮教会.",
}
man = [x for x in json.load(open(os.path.join(H, "..", "photos", "manifest.json"))) if not x.get("track")]
# the phone records the compass heading against magnetic north (GPSImgDirectionRef = M): turn it to true north with
# the declination of the World Magnetic Model 2025 at the photograph's place and time (−7.7°, i.e. 7.7° west, here)
from pygeomag import GeoMag
_WMM = GeoMag(coefficients_file="wmm/WMM_2025.COF")
def true_bearing(x):
    if x["dir"] is None: return None
    if x.get("dir_ref") != "M": return round(x["dir"]) % 360
    y, mo, d = (int(v) for v in x["time"][:10].split(":"))
    import datetime as _dt
    t = _dt.date(y, mo, d); yr = y + (t.timetuple().tm_yday - 0.5) / (366 if y % 4 == 0 else 365)
    return round(x["dir"] + _WMM.calculate(glat=x["lat"], glon=x["lon"], alt=0, time=yr).d) % 360
photos = []
for x in sorted(man, key=lambda x: x["time"]):
    if x["file"] not in CAP: continue
    t = x["time"].replace(":", "").replace(" ", "_")
    px, py = pg(x["lon"], x["lat"])
    w, h = (x["web_w"], x["web_h"])
    sc = 1280 / max(w, h); w2, h2 = round(w * sc), round(h * sc)
    photos.append({"id": x["file"][4:8], "src": f"img/field/{t}.jpg", "thumb": f"img/field/{t}_t.jpg", "w": w2, "h": h2,
                   "x": round(px, 3), "y": round(py, 3), "brg": true_bearing(x),
                   "acc": round(x["hpe_m"], 1) if x["hpe_m"] else None, "time": x["time"][11:16], "cap": CAP[x["file"]]})
# ---- motorways closed to bicycles ----
roads = json.load(open(os.path.join(H, "roads.json")))
mw = []
for e in roads["elements"]:
    t = e.get("tags", {})
    if t.get("highway") in ("motorway",):
        mw.append(simp([pg(q["lon"], q["lat"]) for q in e["geometry"]], 0.08))
mw_names = sorted({e.get("tags", {}).get("name") for e in roads["elements"] if e.get("tags", {}).get("highway") == "motorway" and e.get("tags", {}).get("name")})
json.dump({"photos": photos, "mw": d_of(mw), "mw_names": mw_names, "closures": []},
          open(os.path.join(H, "fn_misc.json"), "w"), ensure_ascii=False)
print("photos", len(photos), "mw", len(mw), mw_names, file=sys.stderr)
