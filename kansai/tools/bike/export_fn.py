"""Write kansai/data/fieldnotes.js (window.__FN): the town ride of 28 Sep 2025 with its photographs, the walk / bike /
car directness of every building in the town core, and the regional bicycle corridors between Hongū, Hayatama and
Nachi with their route families, road-bed profiles, hazards and rain-closure sections. Page units: 1 = 100 m."""
import json, math, os, sys, collections, re
from pyproj import Transformer
from route import Graph, hav
import options as OPT
from pagegeo import TR, O, pgm, pg, fm, d_of, simp
H = os.getcwd()
roads = json.load(open(os.path.join(H, "roads.json"))); G = Graph(roads)
C = {r["id"]: r for r in json.load(open(os.path.join(H, "corridors.json")))}
CH = json.load(open(os.path.join(H, "chains.json")))
SN = {k: int(v) for k, v in CH["snap"].items()}
# ------------------------------- region -------------------------------
def canon(cid):
    r = C[cid]
    for k in sorted(C):
        q = C[k]
        if k < cid and {q["a"], q["b"]} == {r["a"], r["b"]} and abs(q["len_m"] - r["len_m"]) < 0.1 * r["len_m"] and q["refs"][0][0] == r["refs"][0][0]:
            return k
    return cid
DUP = {cid for cid in C if canon(cid) != cid}
UNP = {"ground", "dirt", "gravel", "unpaved", "compacted", "fine_gravel", "earth", "grass", "mud", "sand"}
chains = []
for cid, r in sorted(C.items()):
    if cid in DUP: continue
    ll = [G.xy[n] for n in r["nodes"]]
    P = simp([pg(*p) for p in ll], 0.05)
    prof = r["prof"]; step = 40.0; L = r["len_m"]; hs = []
    k = 0
    for i in range(int(L // step) + 1):
        s = i * step
        while k < len(prof) - 1 and prof[k + 1][0] < s: k += 1
        a, b = prof[k], prof[min(k + 1, len(prof) - 1)]
        f = 0 if b[0] == a[0] else (s - a[0]) / (b[0] - a[0]); hs.append(round(a[1] + (b[1] - a[1]) * max(0, min(1, f))))
    hs.append(round(prof[-1][1]))
    tun = [s for s in r["structures"] if s["kind"] == "tunnel"]
    unp = sum(v for k2, v in r["surf"].items() if k2 in UNP)
    gs = sorted(r["gsi"], key=lambda x: -x[2]); gt = sum(x[2] for x in gs) or 1
    chains.append({"id": cid, "d": d_of([P]), "a": r["a"], "b": r["b"], "len": L, "up": r["up5"], "range_up": [r["up_lo"], r["up_hi"]],
                   "gmax": r["gmax"][0], "tun": [len(tun), sum(s["len"] for s in tun), max((s["len"] for s in tun), default=0)],
                   "unp": unp, "haz": r["haz"], "gsi": [[x[0], x[1], round(x[2] / gt * 100)] for x in gs[:3]],
                   "refs": [x[0] for x in r["refs"] if x[0]][:3], "h": hs, "hmax": r["h_max"], "hmin": r["h_min"], "pcr": r.get("pcr_m", 0)})
# nodes
names = {}
P = json.load(open(os.path.join(os.getcwd(), "..", "geo", "osm", "places.json")))
places = [(e.get("lon") or (e.get("center") or {}).get("lon"), e.get("lat") or (e.get("center") or {}).get("lat"), e["tags"]) for e in P["elements"] if e.get("tags", {}).get("place") in ("village", "hamlet", "suburb", "neighbourhood", "quarter", "town")]
places = [p for p in places if p[0] is not None]
SHR = {"hongu": ("熊野本宮大社", "Kumano Hongū Taisha"), "hayatama": ("熊野速玉大社", "Kumano Hayatama Taisha"), "nachi": ("熊野那智大社", "Kumano Nachi Taisha")}
def kana2rom(t): return t
nodes = []
used = {x for ch in chains for x in (ch["a"], ch["b"])}
for n in used:
    lon, lat = G.xy[n]; x, y = pg(lon, lat)
    sh = [k for k, v in SN.items() if v == n]
    if sh:
        nodes.append({"id": n, "x": round(x, 2), "y": round(y, 2), "ja": SHR[sh[0]][0], "en": SHR[sh[0]][1], "shrine": sh[0]}); continue
    best = min(places, key=lambda p: hav((lon, lat), (p[0], p[1])))
    t = best[2]; ja = re.sub(r"^(本宮町|熊野川町|紀和町|飛鳥町)", "", t.get("name", ""))
    en = re.sub(r"^(Hongucho|Kumanogawacho|Kiwacho|Asukacho)-", "", t.get("name:en", "") or "")
    nodes.append({"id": n, "x": round(x, 2), "y": round(y, 2), "ja": ja, "en": en, "d_m": round(hav((lon, lat), (best[0], best[1])))})
# options
LAB = {}
opts = {}
for a, b in (("hongu", "hayatama"), ("hayatama", "nachi"), ("nachi", "hongu")):
    D, fam = OPT.options(a, b)
    out = []
    seen = set()
    for L, seq in fam:
        seq = [(canon(c), o) for c, o in seq]
        key = tuple(seq)
        if key in seen: continue
        seen.add(key)
        up = sum((C[c]["up5"][0] if o > 0 else C[c]["up5"][1]) for c, o in seq)
        dn = sum((C[c]["up5"][1] if o > 0 else C[c]["up5"][0]) for c, o in seq)
        tun = [sum(len([s for s in C[c]["structures"] if s["kind"] == "tunnel"]) for c, o in seq), sum(sum(s["len"] for s in C[c]["structures"] if s["kind"] == "tunnel") for c, o in seq)]
        unp = sum(sum(v for k2, v in C[c]["surf"].items() if k2 in UNP) for c, o in seq)
        hz = collections.Counter()
        for c, o in seq:
            for k2, v in C[c]["haz"].items(): hz[k2] += v
        gmax = max(abs(C[c]["gmax"][0]) for c, o in seq)
        pcr = sum(C[c].get("pcr_m", 0) for c, o in seq)
        cat = collections.Counter()
        for c, o in seq:
            for k3, w3, v3 in C[c]["gsi"]: cat[k3] += v3
        ct = sum(cat.values()) or 1
        out.append({"seq": seq, "len": round(L), "up": up, "down": dn, "gmax": gmax, "tun": tun, "unp": unp, "haz": dict(hz), "pcr": pcr, "cat": {k3: round(v3 / ct * 100) for k3, v3 in cat.items()}})
        if len(out) >= (8 if a == "hongu" else 6): break
    opts[a + "-" + b] = {"shortest": round(D), "list": out}
    print(a, b, [(o["len"], o["up"], [c for c, _ in o["seq"] if C[c]["len_m"] >= 2000]) for o in out], file=sys.stderr)
json.dump({"chains": chains, "nodes": nodes, "options": opts}, open(os.path.join(H, "fn_region.json"), "w"), ensure_ascii=False)
print("region chains", len(chains), "nodes", len(nodes), "size", len(json.dumps({"chains": chains, "nodes": nodes, "options": opts}, ensure_ascii=False)) // 1024, "KB", file=sys.stderr)
