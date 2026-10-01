"""Designated tsunami evacuation sites, Shingū and Kihō: GSI 指定緊急避難場所 with 津波 = 1 (both towns, updated
2025-01-23), joined to Shingū's 津波一時避難施設・場所 list (2017-02-03) for the height above sea level of the floor or
ground people are sent to. Writes sites.json."""
import csv, json, re, numpy as np
import hz
import cfg
def norm(s):
    s = re.sub(r"[（(].*?[）)]", "", s); s = s.replace("　", "").replace(" ", "")
    for a, b in (("しんぐう", "新宮"), ("ＪＰ", "JP"), ("Ｔ", "T"), ("ターマイト・クリーン", "ターマイトクリーン"), ("附属", "付属"), ("近畿財務局", "")):
        s = s.replace(a, b)
    return s
ichiji = list(csv.DictReader(open("shingu_tsunami_ichiji_2017.csv", encoding="utf-8")))     # citylist.py
# explicit pairs where the names differ beyond normalisation (GSI name -> city 2017 name)
ALIAS = {"新宮市保健センター": "保健センター", "シャトー新宮": "シャトー新宮", "新宮高等学校": "和歌山県立新宮高等学校",
         "城南中学校": "城南中学校", "三輪崎八幡神社": "八幡神社", "宝珠寺境内": "宝珠寺駐車場", "宝珠寺本堂": None,
         "近畿大学付属新宮高等学校中学校": "近畿大学付属新宮高等学校・中学校第1グラウンド", "新宮市人権教育センター": "人権教育センター",
         "新宮市福祉センター": "福祉センター", "天理教南海大教会": "天理教南海大教会駐車場", "三輪崎会館": "三輪崎会館",
         "神倉小学校": "神倉小学校", "光洋中学校": "光洋中学校", "三輪崎小学校": "三輪崎小学校", "王子ヶ浜小学校": "王子ヶ浜小学校",
         "緑丘中学校": "緑丘中学校", "新宮合同宿舎": "新宮合同宿舎"}
icn = {norm(r["施設名"]): r for r in ichiji}
OPEN = re.compile("公園|高台|駐車場|境内|グラウンド|浄水場|競技場|築山|避難場所|キャンプ場")
out = []
for code, muni in (("30207", 1), ("24562", 2)):
    for r in csv.DictReader(open(cfg.dl("sites", f"{code}_2.csv"), encoding="utf-8-sig")):
        if r["津波"] != "1": continue
        name = r["施設・場所名"]; n = norm(name)
        key = ALIAS.get(n, n)
        m = icn.get(norm(key)) if key else None
        lev = None; floor = None
        if m:
            mm = re.match(r"([\d.]+)m", m["海抜"]); lev = float(mm.group(1)) if mm else None; floor = m["指定場所"]
        lon, lat = float(r["経度"]), float(r["緯度"]); x, y = hz.TR(lon, lat)
        out.append({"name": name, "muni": muni, "lon": lon, "lat": lat, "x": x, "y": y, "open": bool(OPEN.search(name)),
                    "level_m": lev, "floor": floor, "city2017": m["施設名"] if m else None})
X = np.array([s["x"] for s in out]); Y = np.array([s["y"] for s in out]); MU = np.array([s["muni"] for s in out])
Z = hz.ground(X, Y); C = hz.tsunami_max(X, Y, MU); F = hz.tsunami_freq(X, Y, MU)
for s, z, c, f in zip(out, Z, C, F):
    s["ground_m"] = round(float(z), 2); s["cls_max"] = int(c); s["cls_freq"] = int(f)
    s["depth_hi"] = float(hz.CLS_HI[c]); s["water_hi"] = round(float(z + hz.CLS_HI[c]), 2) if c else None
    # height people climb: to the listed floor if known; otherwise above the 2026 maximum depth class at the site
    if s["level_m"] is not None and not s["open"]:
        s["climb_m"] = round(max(0.0, s["level_m"] - z), 2)
    elif c and not s["open"]:
        s["climb_m"] = float(hz.CLS_HI[c])
    else:
        s["climb_m"] = 0.0
    # still above the 2026 maximum? (listed level vs ground + upper bound of the class)
    if c == 0: s["safe_2026"] = "outside"
    elif s["level_m"] is not None: s["safe_2026"] = "yes" if s["level_m"] >= z + hz.CLS_HI[c] else ("no" if s["level_m"] < z + hz.CLS_LO[c] else "class")
    else: s["safe_2026"] = "unknown"
json.dump(out, open("sites.json", "w"), ensure_ascii=False, indent=0)
import collections
for m in (1, 2):
    ss = [s for s in out if s["muni"] == m]
    print(m, len(ss), "matched level", sum(s["level_m"] is not None for s in ss), "inside 2026 max", sum(s["cls_max"] > 0 for s in ss),
          collections.Counter(s["safe_2026"] for s in ss))
for s in out:
    if s["cls_max"] > 0:
        print(" ", s["muni"], s["name"], "cls", s["cls_max"], "ground", s["ground_m"], "level", s["level_m"], "safe", s["safe_2026"], "open", s["open"])
print("unmatched city 2017 names:", sorted(set(r["施設名"] for r in ichiji) - set(s["city2017"] for s in out if s["city2017"])))
