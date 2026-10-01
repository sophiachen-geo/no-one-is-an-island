"""Download every input of the risk analysis that the main build and tools/tsunami2026 do not already provide, into
./downloads (or RISK_DOWNLOADS). Files already present are kept. Fetched for the page on 2026-10-01.
  e-Stat (総務省統計局), 2020 census: 250 m mesh, population and households (T001142) and five-year ages (T001196), first-level
    meshes 5035 and 5036; small areas (町丁・字等) of 新宮市 (30207) and 紀宝町 (24562): boundaries (JGD2011) and ages (T001082).
  GSI 指定緊急避難場所データ: 新宮市 and 紀宝町 (CSV, updated 2025-01-23).
  Shingū City: 避難（津波一時避難施設・場所）, https://www.city.shingu.lg.jp/info/762 (updated 2017-02-03).
  MLIT 国土数値情報 P04 医療機関 (2020): Wakayama, Mie.
  IPSS 日本の地域別将来推計人口（令和5年推計）: total, 65+, 75+ by municipality.
  OpenStreetMap (Overpass): sites that are not homes (schools, temples and shrines, industry, retail, …) in the study area."""
import os, sys, json, ssl, time, urllib.request, urllib.parse
import cfg
D = cfg.DL
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
ES = "https://www.e-stat.go.jp/gis/statmap-search/data"
FILES = {
    "census2020_mesh/tblT001142Q5035.zip": f"{ES}?statsId=T001142&code=5035&downloadType=2",
    "census2020_mesh/tblT001142Q5036.zip": f"{ES}?statsId=T001142&code=5036&downloadType=2",
    "census2020_mesh/tblT001196Q5035.zip": f"{ES}?statsId=T001196&code=5035&downloadType=2",
    "census2020_mesh/tblT001196Q5036.zip": f"{ES}?statsId=T001196&code=5036&downloadType=2",
    "census2020_smallarea/A002005212020DDSWC30207-JGD2011.zip": f"{ES}?dlserveyId=A002005212020&code=30207&coordSys=1&format=shape&downloadType=5&datum=2011",
    "census2020_smallarea/A002005212020DDSWC24562-JGD2011.zip": f"{ES}?dlserveyId=A002005212020&code=24562&coordSys=1&format=shape&downloadType=5&datum=2011",
    "census2020_smallarea/tblT001082C30.zip": f"{ES}?statsId=T001082&code=30&downloadType=2",
    "census2020_smallarea/tblT001082C24.zip": f"{ES}?statsId=T001082&code=24&downloadType=2",
    "sites/30207_2.csv": "https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/30207_2.csv",
    "sites/24562_2.csv": "https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/24562_2.csv",
    "sites/shingu_info_762.html": "https://www.city.shingu.lg.jp/info/762",
    "ksj/P04-20_30_GML.zip": "https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_30_GML.zip",
    "ksj/P04-20_24_GML.zip": "https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_24_GML.zip",
    "ipss2023/kekkahyo1.xlsx": "https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/2gaiyo_hyo/kekkahyo1.xlsx",
    "ipss2023/kekkahyo2_3.xlsx": "https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/2gaiyo_hyo/kekkahyo2_3.xlsx",
    "ipss2023/kekkahyo2_4.xlsx": "https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/2gaiyo_hyo/kekkahyo2_4.xlsx",
}
ctx = ssl.create_default_context()
ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)      # some government hosts need legacy renegotiation (verification stays on)
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
for rel, url in FILES.items():
    f = os.path.join(D, rel); os.makedirs(os.path.dirname(f), exist_ok=True)
    if os.path.exists(f) and os.path.getsize(f) > 0: continue
    for a in range(4):
        try:
            data = op.open(urllib.request.Request(url, headers=UA), timeout=300).read(); open(f, "wb").write(data); print(rel, len(data)); break
        except Exception as e:
            print("retry", rel, repr(e)[:120], file=sys.stderr); time.sleep(3 * (a + 1))
# OpenStreetMap: land use and amenities that are not homes (the dasymetric weights leave their buildings out)
f = os.path.join(D, "osm_nonres.json")
if not os.path.exists(f):
    sys.path.insert(0, cfg.BIKE); from fetch import run
    BB = "33.66,135.77,33.90,136.05"
    run(f'''[out:json][timeout:300];(
way["landuse"~"^(industrial|commercial|retail|railway|military|cemetery|religious|port|quarry|landfill|garages)$"]({BB});
relation["landuse"~"^(industrial|commercial|retail|railway|military|cemetery|religious|port)$"]({BB});
way["amenity"~"^(school|college|university|kindergarten|hospital|clinic|place_of_worship|townhall|fire_station|police|community_centre|library|parking|marketplace|post_office|courthouse|prison)$"]({BB});
relation["amenity"~"^(school|college|university|kindergarten|hospital|place_of_worship|townhall|parking)$"]({BB});
way["leisure"~"^(park|pitch|sports_centre|stadium|track|swimming_pool|golf_course)$"]({BB});
way["building"~"^(school|industrial|warehouse|commercial|retail|public|temple|shrine|church|hospital|train_station|office|civic|government|kindergarten|university|supermarket|factory|hangar|garage|garages|shed|roof|parking|religious)$"]({BB});
way["tourism"~"^(hotel|museum)$"]({BB});
);out body geom qt;''', f)
