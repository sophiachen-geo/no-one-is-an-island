"""Map the rain-closure sections onto the road network along their own road number, then onto the corridors.

Wakayama: 異常気象時通行規制区間 (open data, start and end points; 通行止め at a continuous-rain threshold).
Mie:      雨量規制区間 (pref.mie.lg.jp, section sheets; 通行止め at 40 mm/h or a continuous-rain threshold). Mie gives
          places, not points: a section that is a whole road runs between the road's own ends; otherwise between
          GSI's place annotations (Anno 210) or OSM place nodes, and the drawn stretch is the road between those places.
MLIT (Route 42): every 異常気象時通行止区間 of 紀南河川国道事務所 lies west of this frame (串本–みなべ), none here."""
import json, os, re, sys, heapq, collections
from route import Graph, hav
from pagegeo import pg, d_of, simp
H = os.getcwd(); R = os.environ.get("BIKE_RESEARCH", os.environ.get("BIKE_RESEARCH", os.path.join(os.getcwd(), "..", "research", "bike")))
roads = json.load(open(os.path.join(H, "roads.json"))); G = Graph(roads)
C = {r["id"]: r for r in json.load(open(os.path.join(H, "corridors.json")))}
node_chain = {}
for cid, r in C.items():
    for n in r["nodes"]: node_chain.setdefault(n, set()).add(cid)
def refs(w): return (G.ways[w].get("tags", {}).get("ref") or "").replace("；", ";").split(";")
def along(ref, s, t):
    """Shortest path from node s to node t on ways carrying this road number (either direction)."""
    ok = lambda w: ref in refs(w)
    und = collections.defaultdict(list)
    for u, lst in G.adj.items():
        for v, L, w, i in lst:
            if ok(w): und[u].append((v, L)); und[v].append((u, L))
    dist = {s: 0.0}; prev = {}; pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t: break
        if d > dist[u]: continue
        for v, L in und[u]:
            if d + L < dist.get(v, 1e18): dist[v] = d + L; prev[v] = u; heapq.heappush(pq, (d + L, v))
    if t not in dist: return None, None
    path = [t]
    while path[-1] != s: path.append(prev[path[-1]])
    return path[::-1], dist[t]
def ref_nodes(ref): return [n for n, lst in G.adj.items() if any(ref in refs(w) for _, _, w, _ in lst)]
def snap(ref, lo, la):
    n = min(ref_nodes(ref), key=lambda n: hav(G.xy[n], (lo, la))); return n, hav(G.xy[n], (lo, la))
def road_ends(ref):
    nb = collections.defaultdict(set)
    for u, lst in G.adj.items():
        for v, L, w, i in lst:
            if ref in refs(w): nb[u].add(v); nb[v].add(u)
    return [u for u in nb if len(nb[u]) == 1]
def record(no, pref, road, where, mm, hr, risk, path, L, snap_m, extra=None):
    on = {}
    for a, b in zip(path, path[1:]):
        for cid in (node_chain.get(a, set()) & node_chain.get(b, set())):
            on[cid] = on.get(cid, 0) + hav(G.xy[a], G.xy[b])
    rec = {"no": no, "pref": pref, "road": road, "where": where, "mm": mm, "hr": hr, "risk": risk, "len": round(L), "snap_m": snap_m,
           "chains": {str(k): round(v) for k, v in on.items()}, "d": d_of([simp([pg(*G.xy[n]) for n in path], 0.05)]),
           "mid": [round(v, 2) for v in pg(*G.xy[path[len(path) // 2]])]}
    if extra: rec.update(extra)
    print(pref, no, road, where, mm, "mm", ("/ %d mm/h" % hr) if hr else "", "|", round(L), "m | ends snapped", snap_m, "| on corridors", rec["chains"], file=sys.stderr)
    return rec
out = []
# ---------------- Wakayama: start and end points of each section ----------------
REF = {"国道１６８号": "168", "那智山勝浦線": "46", "那智勝浦古座川線": "43"}
rc = json.load(open(os.path.join(R, "wakayama_ijoukisho_kisei.geojson")))
by = {}
for f in rc["features"]:
    lo, la = f["geometry"]["coordinates"][:2]
    if 135.70 <= lo <= 136.06 and 33.60 <= la <= 33.92:
        by.setdefault(f["properties"]["No"], {"p": f["properties"], "pts": []})["pts"].append((lo, la))
for no, v in sorted(by.items(), key=lambda kv: int(kv[0])):
    p = v["p"]; ref = REF.get(p["路線名"]); mm = int(re.search(r"(\d+)mm", p["規制条件"]).group(1))
    if ref is None:
        print("no road number for", p["路線名"], file=sys.stderr); continue
    (s, ds), (t, dt) = snap(ref, *v["pts"][0]), snap(ref, *v["pts"][1])
    path, L = along(ref, s, t)
    if path is None:
        print("no path", no, file=sys.stderr); continue
    out.append(record(no, "Wakayama", p["路線名"], p["地先名"], mm, None, p["危険内容"], path, L, [round(ds), round(dt)]))
# ---------------- Mie: 雨量規制区間 in the frame on roads the corridors use ----------------
# places: GSI 最適化ベクトルタイル Anno (vt_code 210, 大字) and OSM place nodes; Mie gives 起点/終点 by 大字
PLACE = {"紀和町小栗須": (135.92366, 33.87137), "紀和町矢ノ川": (135.94582, 33.86345),   # GSI Anno 210
         "御浜町上野": (135.983067, 33.8530269), "紀宝町鮒田": (135.97999, 33.74485)}       # OSM node 8434883907; GSI Anno 210
MIE = [  # no, road, ref, where, km (Mie), mm, mm/h, ends ('end:<lon,lat>' = the road's own end nearest that point)
    ("三重44", "小船紀宝線", "740", "熊野市紀和町小船～南牟婁郡紀宝町鮒田", 23.1, 200, 40, ("end:135.86,33.84", "end:135.98,33.74")),
    ("三重14", "国道311号", "311", "熊野市紀和町矢ノ川～熊野市紀和町小栗須", 1.1, 200, 40, ("紀和町矢ノ川", "紀和町小栗須")),
    ("三重36", "御浜紀和線", "62", "南牟婁郡御浜町阿田和～南牟婁郡御浜町上野", 9.8, 200, 40, ("end:136.04,33.80", "御浜町上野")),
]
for no, road, ref, where, km, mm, hr, (ea, eb) in MIE:
    ends = []
    for e in (ea, eb):
        if e.startswith("end:"):
            lo, la = map(float, e[4:].split(","))
            n = min(road_ends(ref), key=lambda n: hav(G.xy[n], (lo, la))); ends.append((n, 0.0))
        else:
            ends.append(snap(ref, *PLACE[e]))
    path, L = along(ref, ends[0][0], ends[1][0])
    if path is None:
        print("no path", no, file=sys.stderr); continue
    out.append(record(no, "Mie", road, where, mm, hr, "", path, L, [round(e[1]) for e in ends], {"km_official": km, "between_places": not (ea.startswith("end:") and eb.startswith("end:"))}))
m = json.load(open(os.path.join(H, "fn_misc.json"))); m["closures"] = out
json.dump(m, open(os.path.join(H, "fn_misc.json"), "w"), ensure_ascii=False)
