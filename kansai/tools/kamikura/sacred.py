"""Kamikura micro-study: the religious flow (信仰). Called by 09_export.py; run from the same work directory.

Locates the religious features at the foot of Kamikura-yama and on its steps, measures the climb on GSI DEM1A, and
builds a vertical section from Gotobiki-iwa through Kumano Hayatama Taisha to the Kumano River and the sea.

Sources
  OSM       osm.json (step 1): the steps (way 121366071) and the path to the rock (way 121369321); the steles,
            boards and small shrines at the foot and on the steps; the two precinct polygons at the entrance —
            way 500803106 is 神倉神社's lower precinct, way 500803107 holds the 出雲大社新宮教会 (its building
            way 499568822, its torii and its board) and is not part of the shrine.
  DEM1A     terrain.npz (step 2): the 1 m bare-ground model of the frame.
  DEM5A     ../gsi_dem5.npy + ../gsi_dem5.json (the main build's 5 m mosaic of the city, z15 tiles) for the section
            beyond the frame.
  GSI       optimal vector tiles (../morph/raw/bvmap/z16): water areas (ftCode 5000: the river and the sea), roads
            (27xx centre lines), the railway (8201) and the 1:25,000 contours (7351) for the town figure; the water
            area fixes the river bank nearest Hayatama.
  Streets   osm_streets_hayatama.json: every OSM highway between Kamikura and Hayatama (Overpass, fetched once and
            kept); the walk from the foot of the steps to Hayatama is the shortest path on it (trunk roads excluded).
  Rivers    osm_rivers_town.json: OSM waterways and coastline of the town (Overpass, fetched once and kept). The
            Kumano's centre line (way 59234786, from MLIT 国土数値情報 W05) meets the coastline at the river mouth;
            distances on the river are measured along it. 市田川 is OSM's five ways of that name.
The section is measured from the rock to the river bank by Hayatama. Beyond it the river is at sea level and GSI's
5 m model has no data over water, so the reach to the sea is drawn as a labelled break, its length along the river
given. Every label written here has an independent reference in kansai/qa/points.toml (kmk_*, kmc_*).
"""
import json, math, os
import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import Point, LineString, Polygon, shape
from shapely.ops import unary_union, nearest_points, transform, linemerge, substring
from pyproj import Transformer

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
P2LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)
STEPS, PATH = 121366071, 121369321
PRECINCT, IZUMO_GROUND, IZUMO_HALL = 500803106, 500803107, 499568822
NODES = {"rock": 4908398809, "naka_jizo": 4908399232, "hi_jinja": 4908399231, "manzan": 4908398790,
         "iwatate": 4908399260, "sarutahiko": 4908399267, "ujo": 4908399262, "geba": 4908399279,
         "izumo_torii": 4908399301}
SHRINE_ROOFS = [494788839, 499575452, 499575460, 499575461]     # small shrine buildings (OSM wayside_shrine)
HAYATAMA = (135.98368, 33.73230)                                   # points.toml hayatama (OSM way 211578006)
ASUKA = (135.997083, 33.728757)                                    # OSM way 499565075 阿須賀神社 (centroid)
MYOSHIN = (135.984329, 33.724781)                                  # points.toml kmk_myoshin
MIFUNEJIMA = (135.97320, 33.73595)                                 # points.toml mifunejima
OJI = (136.002073, 33.717135)                                      # OSM node 6853147598 王子神社 (浜王子跡)
KOYAZAKA = (135.991451, 33.701654)                                 # OSM node 7607892185 高野坂 (beyond the figure)
GONGEN = (135.9798175, 33.7278248)                                 # OSM node 4355134042 権現山 (千穂ヶ峯), ele 253
SCHOOL = 1333972521                                                # OSM way: the school compound (神倉小学校)
KUMANO = 59234786                                                  # OSM way: the Kumano's centre line
TOWN_LL = (135.966, 33.7135, 136.020, 33.7425)                     # the town figure: Mifune-jima to the river mouth


def _osm(osm_path="osm.json"):
    E = json.load(open(osm_path))["elements"]
    ways = {e["id"]: e for e in E if e["type"] == "way" and e.get("geometry")}
    nodes = {e["id"]: e for e in E if e["type"] == "node"}
    return ways, nodes


def _line(w): return LineString([LL2P.transform(p["lon"], p["lat"]) for p in w["geometry"]])


def _poly(w): return Polygon([LL2P.transform(p["lon"], p["lat"]) for p in w["geometry"]])


def _pt(n): return Point(*LL2P.transform(n["lon"], n["lat"]))


def _zat(zf, x0, y1):
    def f(x, y):
        return float(ndi.map_coordinates(zf, [[y1 - 0.5 - y], [x - x0 - 0.5]], order=1, mode="nearest")[0])
    return f


def _dem5(path_npy="../gsi_dem5.npy", path_meta="../gsi_dem5.json"):
    """The main build's DEM5A mosaic (web-mercator z15 pixels) → height at a CS VI point."""
    g = np.load(path_npy); m = json.load(open(path_meta)); z = m["z"]; n = 2 ** z
    def f(x, y):
        lon, lat = P2LL.transform(x, y)
        px = (lon + 180) / 360 * n * 256 - m["tx0"] * 256
        py = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * 256 - m["ty0"] * 256
        v = ndi.map_coordinates(np.nan_to_num(g, nan=-9999.0), [[py - 0.5], [px - 0.5]], order=1, mode="nearest")[0]
        return float(v) if v > -100 else float("nan")
    return f


def _gsi(layer, codes, bbox, tiles="../morph/raw/bvmap/z16"):
    import mapbox_vector_tile
    n = 2 ** 16
    def tile(lon, lat):
        return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    (tx0, ty0), (tx1, ty1) = tile(bbox[0], bbox[3]), tile(bbox[2], bbox[1])
    out = []
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            f = f"{tiles}/16_{tx}_{ty}.pbf"
            if not os.path.exists(f): continue
            t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
            L = t.get(layer)
            if not L: continue
            ext = L["extent"]
            for ft in L["features"]:
                if ft["properties"].get("ftCode") not in codes: continue
                def tr(x, y, z=None, tx=tx, ty=ty):
                    X = (tx + np.asarray(x) / ext) / n; Y = (ty + np.asarray(y) / ext) / n
                    return LL2P.transform(X * 360 - 180, np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * Y)))))
                out.append(transform(tr, shape(ft["geometry"])))
    return out


def _streets(path="osm_streets_hayatama.json"):
    if not os.path.exists(path):
        import urllib.parse, urllib.request
        q = '[out:json][timeout:90];way["highway"](33.7200,135.9770,33.7360,135.9930);out geom;'
        req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "no-one-is-an-island kansai/tools/kamikura"})
        open(path, "wb").write(urllib.request.urlopen(req, timeout=180).read())
    return json.load(open(path))


def _town(path="osm_rivers_town.json"):
    """OSM waterways and coastline of the town (Overpass, fetched once and kept)."""
    if not os.path.exists(path):
        import time, urllib.parse, urllib.request
        q = ('[out:json][timeout:90];(way["waterway"~"river|canal|stream|drain"](33.700,135.960,33.750,136.030);'
             'way["natural"="coastline"](33.700,135.960,33.750,136.030););out geom tags;')
        for k in range(4):
            try:
                req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": "no-one-is-an-island kansai/tools/kamikura"})
                open(path, "wb").write(urllib.request.urlopen(req, timeout=180).read()); break
            except OSError:
                time.sleep(4 * 2 ** k)
    E = json.load(open(path))["elements"]
    lines = lambda es: [LineString([LL2P.transform(p["lon"], p["lat"]) for p in e["geometry"]]) for e in es]
    kumano = lines([e for e in E if e["id"] == KUMANO])[0]
    coast = unary_union(lines([e for e in E if e["tags"].get("natural") == "coastline"]))
    ichida = linemerge(unary_union(lines([e for e in E if e["tags"].get("name") == "市田川"])))
    mouth = kumano.intersection(coast)
    mouth = min(getattr(mouth, "geoms", [mouth]), key=lambda p: p.distance(Point(kumano.coords[-1])))
    return kumano, coast, ichida, mouth


def _walk(a, b):
    """Shortest walk on the OSM street network between two CS VI points (trunk roads excluded)."""
    import networkx as nx
    G, xy = nx.Graph(), {}
    for w in _streets()["elements"]:
        if w["type"] != "way" or w["tags"].get("highway") in ("trunk", "trunk_link", "motorway", "motorway_link"): continue
        for n0, n1, g0, g1 in zip(w["nodes"], w["nodes"][1:], w["geometry"], w["geometry"][1:]):
            p0, p1 = LL2P.transform(g0["lon"], g0["lat"]), LL2P.transform(g1["lon"], g1["lat"])
            xy[n0], xy[n1] = p0, p1; G.add_edge(n0, n1, w=math.dist(p0, p1))
    na = min(xy, key=lambda n: math.dist(xy[n], (a.x, a.y))); nb = min(xy, key=lambda n: math.dist(xy[n], (b.x, b.y)))
    return LineString([xy[n] for n in nx.shortest_path(G, na, nb, weight="w")])


def build(z, x0, y1, frame, st, pg, path, foot=None):
    """Everything the religious flow needs: map layers (page paths), labels, and data for its figures."""
    ways, nodes = _osm()
    zf = np.where(np.isnan(z), np.nanmedian(z), z); zat = _zat(zf, x0, y1)
    tr = LineString(st["transect"])
    N = {k: _pt(nodes[v]) for k, v in NODES.items()}

    # ---- the climb: the steps, measured on DEM1A (OSM draws them from the foot upwards)
    S = _line(ways[STEPS]); Pt = _line(ways[PATH])
    ds = np.arange(0, S.length, 1.0); zs = np.array([zat(*S.interpolate(d).coords[0]) for d in ds])
    gain = float(zs.max() - zs.min())
    w10 = [abs(zs[i + 10] - zs[i]) / 10 for i in range(len(zs) - 10)]; i10 = int(np.argmax(w10))
    jizo_s = S.project(N["naka_jizo"]); j = int(round(jizo_s))
    lower = (float(zs[j] - zs[0]), float(jizo_s)); upper = (float(zs[-1] - zs[j]), float(S.length - jizo_s))
    climb = {"steps_len_m": round(S.length, 1), "z_foot": round(float(zs[0]), 1), "z_top": round(float(zs[-1]), 1),
             "gain_m": round(gain, 1), "mean_deg": round(math.degrees(math.atan(gain / S.length)), 1),
             "steep10_deg": round(math.degrees(math.atan(max(w10))), 1), "steep10_from_foot_m": i10,
             "lower": {"to": "中ノ地蔵堂", "len_m": round(lower[1], 1), "gain_m": round(lower[0], 1), "deg": round(math.degrees(math.atan(lower[0] / lower[1])), 1)},
             "upper": {"len_m": round(upper[1], 1), "gain_m": round(upper[0], 1), "deg": round(math.degrees(math.atan(upper[0] / upper[1])), 1)},
             "path_len_m": round(Pt.length, 1)}

    # ---- the threshold sequence: where each element lies along the transect (metres from Gotobiki-iwa) and how high
    def along(p): return round(tr.project(p), 1)
    seq = [["rock", "Gotobiki-iwa", along(N["rock"])], ["manzan", "満山社", along(N["manzan"])],
           ["top", "top of the steps", along(Point(S.coords[-1]))], ["jizo", "中ノ地蔵堂", along(N["naka_jizo"])],
           ["foot", "foot of the steps", along(Point(S.coords[0]))], ["iwatate", "天磐盾 stele", along(N["iwatate"])],
           ["sarutahiko", "猿田彦神社・神倉三宝荒神社", along(N["sarutahiko"])], ["geba", "下馬 stone", along(N["geba"])]]
    for q in seq: q.append(round(zat(*tr.interpolate(q[2]).coords[0]), 1))
    # every stele, board, torii and shrine OSM maps within 12 m of the line, as far as the 下馬 stone
    def kind(t):
        if t.get("historic") == "memorial": return "stele"
        if t.get("information") == "board": return "board"
        if t.get("man_made") == "ceremonial_gate": return "torii"
        if t.get("amenity") == "place_of_worship": return "shrine"
    end_d = tr.project(N["geba"]) + 2
    markers = sorted([round(tr.project(p), 1), k, n["tags"].get("name", "")] for n in nodes.values()
                     for k in [kind(n.get("tags", {}))] if k for p in [_pt(n)] if tr.distance(p) <= 12 and tr.project(p) <= end_d)
    markers += sorted([round(tr.project(_poly(ways[w]).centroid), 1), "shrine", ""] for w in SHRINE_ROOFS)
    markers.sort()
    f0, f1 = seq[4][2] - 5, seq[7][2] + 1                       # the last stretch: from 5 m above the foot of the steps to the 下馬 stone
    climb["markers_n"] = len(markers); climb["foot_n"] = sum(1 for m in markers if f0 <= m[0] <= f1); climb["foot_span_m"] = round(f1 - f0)
    climb["path_gain_m"] = round(seq[0][3] - climb["z_top"], 1)  # from the top of the steps to the rock

    # ---- the grounds at the entrance: the shrine's lower precinct and, beside it, the Izumo church
    prec, izu = _poly(ways[PRECINCT]), _poly(ways[IZUMO_GROUND])
    poly = Polygon(st["poly"][0])
    climb["steps_in_area_m"] = round(S.intersection(poly).length, 1)          # the part of the steps inside the study area
    grounds = {"precinct_m2": round(prec.intersection(poly).area), "izumo_m2": round(izu.intersection(poly).area),
               "izumo_hall_in_izumo": bool(izu.contains(_poly(ways[IZUMO_HALL]).representative_point())),
               "izumo_torii_in_izumo": bool(izu.contains(N["izumo_torii"])), "precinct_holds_izumo": bool(prec.intersects(_poly(ways[IZUMO_HALL])))}

    # ---- the vertical section: rock → foot of the steps → Hayatama → the Kumano River (its mouth: a labelled break)
    hay = Point(*LL2P.transform(*HAYATAMA))
    bbox = (135.975, 33.712, 136.015, 33.740)
    water = unary_union([g.buffer(0) for g in _gsi("waterarea", (5000,), bbox)])
    river = max(getattr(water, "geoms", [water]), key=lambda g: g.area)       # the river, joined to the sea
    kumano, coast, ichida, mouth = _town()
    bank = nearest_points(hay, river)[1]
    foot_pt = Point(S.coords[0])
    dem5 = _dem5()
    def z_any(x, y):
        inside = x0 <= x <= x0 + z.shape[1] and y1 - z.shape[0] <= y <= y1
        return zat(x, y) if inside else dem5(x, y)
    down = LineString([tr.interpolate(d).coords[0] for d in np.arange(0, tr.project(foot_pt) + 0.01, 2.0)])   # the transect: path and steps
    walk = _walk(foot_pt, hay)
    legs = [("Gotobiki-iwa", "the foot of the steps", down),
            ("the foot of the steps", "Kumano Hayatama Taisha", walk),
            ("Kumano Hayatama Taisha", "the Kumano River", LineString([hay, bank]))]
    prof, stations, d0 = [], [], 0.0
    for a, b, L in legs:
        stations.append([a, round(d0, 1)])
        for d in np.arange(0, L.length, 2.0):
            p = L.interpolate(d); v = z_any(p.x, p.y)
            prof.append([round(float(d0 + d), 1), None if not math.isfinite(v) else round(float(v), 2)])   # no data over water
        d0 += L.length
    stations.append([legs[-1][1], round(d0, 1)])
    section = {"stations": stations, "profile": prof, "length_m": round(d0), "walk_m": round(walk.length),
               "rock_to_hayatama_m": round(N["rock"].distance(hay)), "hayatama_to_river_m": round(hay.distance(river)),
               "river_to_mouth_m": round(kumano.project(mouth) - kumano.project(hay)),
               "hayatama_ground_m": round(dem5(hay.x, hay.y), 1),
               "mouth_ll": [round(v, 6) for v in P2LL.transform(mouth.x, mouth.y)], "bank_ll": [round(v, 6) for v in P2LL.transform(bank.x, bank.y)]}

    # ---- pointers from the foot of the steps to places beyond the frame
    def pointer(lonlat, name):
        q = Point(*LL2P.transform(*lonlat)); dx, dy = q.x - foot_pt.x, q.y - foot_pt.y
        return {"name": name, "dist_m": round(foot_pt.distance(q)), "bearing": round((math.degrees(math.atan2(dx, dy)) + 360) % 360)}
    pointers = {"hayatama": pointer(HAYATAMA, "熊野速玉大社"), "asuka": pointer(ASUKA, "阿須賀神社"),
                "river_end": pointer(tuple(section["mouth_ll"]), "the mouth of the Kumano")}

    # ---- map layers (page units)
    layers = {"precinct": path([list(prec.exterior.coords)], closed=True), "izumo": path([list(izu.exterior.coords)], closed=True),
              "ritual": path([list(S.coords)[::-1], list(Pt.coords)]),
              "shrines": path([list(_poly(ways[w]).exterior.coords) for w in SHRINE_ROOFS], closed=True)}
    # ---- the system's own view: the rock, the steps and the grounds at the foot (and 妙心寺 beside them), 25 m around
    myo = Point(*LL2P.transform(135.984329, 33.724781))                      # points.toml kmk_myoshin
    b = unary_union([N["rock"], S, Pt, prec, izu, myo]).buffer(25).bounds
    home = [round(v, 4) for v in (*pg(b[0], b[3]), *pg(b[2], b[1]))]
    town = circuit(st, ways, N, S, Pt, foot_pt, hay, kumano, coast, ichida, mouth)
    return layers, {"climb": climb, "sequence": seq, "markers": markers, "grounds": grounds, "section": section,
                    "pointers": pointers, "town": town, "home": home, "foot_pg": [round(v, 4) for v in pg(foot_pt.x, foot_pt.y)]}


def circuit(st, ways, N, S, Pt, foot_pt, hay, kumano, coast, ichida, mouth):
    """The town figure: water, contours, roads and railway as the ground; the places of the religious flows; and the
    flows themselves — the river and the pilgrims' order of visits, the 6 February programme, Hayatama's god going
    upriver to Mifune-jima, the water from Kamikura-yama to the sea. Coordinates in metres from the frame's top-left
    corner, y down."""
    from shapely.geometry import box
    (X0, Y0), (X1, Y1) = LL2P.transform(TOWN_LL[0], TOWN_LL[1]), LL2P.transform(TOWN_LL[2], TOWN_LL[3])
    F = box(X0, Y0, X1, Y1)
    def loc(x, y): return [round(x - X0), round(Y1 - y)]
    def lines(g, tol=2.0, min_area=0.0):
        g = g.intersection(F)
        if g.geom_type in ("MultiLineString", "GeometryCollection") and all(h.geom_type == "LineString" for h in getattr(g, "geoms", [])):
            g = linemerge(g)                                                     # rejoin lines cut at tile edges
        g = g.simplify(tol)
        out = []
        for h in getattr(g, "geoms", [g]):
            if h.is_empty: continue
            if h.geom_type == "Polygon" and h.area >= min_area: out += [[loc(*c) for c in r.coords] for r in [h.exterior, *h.interiors]]
            elif h.geom_type == "LineString": out.append([loc(*c) for c in h.coords])
        return [l for l in out if len(l) > 1]
    def enc(ls):
        """SVG path data, integer metres, relative moves: the compact form the page draws directly."""
        out = []
        for l in ls:
            q = [l[0]] + [p for a, p in zip(l, l[1:]) if p != a]
            out.append("M%d %d" % tuple(q[0]) + "".join("l%d %d" % (b[0] - a[0], b[1] - a[1]) for a, b in zip(q, q[1:])))
        return "".join(out)
    bb = (TOWN_LL[0] - 0.003, TOWN_LL[1] - 0.003, TOWN_LL[2] + 0.003, TOWN_LL[3] + 0.003)
    water = unary_union([g.buffer(0) for g in _gsi("waterarea", (5000,), bb)])
    import mapbox_vector_tile                                                   # contours, roads, railway: by attribute
    n = 2 ** 16
    def tile(lon, lat):
        return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    (tx0, ty0), (tx1, ty1) = tile(bb[0], bb[3]), tile(bb[2], bb[1])
    feats = {"contour": [], "road": [], "railway": []}
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            f = f"../morph/raw/bvmap/z16/16_{tx}_{ty}.pbf"
            if not os.path.exists(f): continue
            t = mapbox_vector_tile.decode(open(f, "rb").read(), default_options={"y_coord_down": True})
            for layer in feats:
                L = t.get(layer)
                if not L: continue
                ext = L["extent"]
                for ft in L["features"]:
                    def tr(x, y, z=None, tx=tx, ty=ty):
                        X = (tx + np.asarray(x) / ext) / n; Y = (ty + np.asarray(y) / ext) / n
                        return LL2P.transform(X * 360 - 180, np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * Y)))))
                    feats[layer].append((ft["properties"], transform(tr, shape(ft["geometry"]))))
    contours = {}
    for pr, g in feats["contour"]:
        a = pr.get("alti")
        if pr.get("ftCode") == 7351 and a and a % 40 == 0: contours.setdefault(a, []).append(g)          # every 40 m
    roads = {}
    for pr, g in feats["road"]:
        if pr.get("ftCode") in (2701, 2703, 2711, 2721) and (pr.get("rdCtg") in (0, 1) or (pr.get("rnkWidth") or 0) >= 1):
            roads.setdefault(1 if pr.get("rdCtg") in (0, 1) else 0, []).append(g)       # national and prefectural; others 3 m or wider
    rail = [g for pr, g in feats["railway"] if pr.get("ftCode") == 8201 and pr.get("railState") in (0, None)]
    asuka, myo, mif, oji, koya, gon = (Point(*LL2P.transform(*c)) for c in (ASUKA, MYOSHIN, MIFUNEJIMA, OJI, KOYAZAKA, GONGEN))
    school = _poly(ways[SCHOOL]).representative_point()
    kin = kumano.intersection(F); kin = max(getattr(kin, "geoms", [kin]), key=lambda g: g.length)
    s_hay, s_mif, s_mouth = kumano.project(hay), kumano.project(mif), kumano.project(mouth)
    s_west = kumano.project(Point(kin.coords[0]))
    conf = Point(ichida.coords[-1])                                           # 市田川 ends in the Kumano's estuary
    s_lab = s_hay + 900; a, b = kumano.interpolate(s_lab - 60), kumano.interpolate(s_lab + 60)
    chan = unary_union([LineString(st["ichida"]), _line(ways[499568828])])          # the channel and the Kamikura-yama stream
    place = {"rock": N["rock"], "foot": foot_pt, "hayatama": hay, "asuka": asuka, "myoshin": myo, "mifunejima": mif,
             "oji": oji, "mouth": mouth, "school": school, "gongen": gon, "confluence": conf, "kumano_lab": kumano.interpolate(s_lab),
             "abreast_hay": kumano.interpolate(s_hay), "abreast_mif": kumano.interpolate(s_mif)}
    dx, dy = koya.x - oji.x, koya.y - oji.y
    return {"size": [round(X1 - X0), round(Y1 - Y0)], "origin": [round(X0, 2), round(Y1, 2)],
            "water": enc(lines(water, 3, min_area=5000)),
            "contours": [[a, enc(lines(unary_union(g), 6))] for a, g in sorted(contours.items()) if not unary_union(g).intersection(F).is_empty],
            "roads": [[k, enc(lines(unary_union(g), 4))] for k, g in sorted(roads.items())], "rail": enc(lines(unary_union(rail), 4)),
            "ichida": enc(lines(ichida)), "channel": enc(lines(chan, 1)), "steps": enc(lines(unary_union([S, Pt]), 1)),
            "places": {k: loc(p.x, p.y) for k, p in place.items()},
            "river_in": enc(lines(substring(kumano, s_west, s_hay))), "mifune": enc(lines(substring(kumano, s_mif, s_hay))),
            "to_sea": enc(lines(LineString([conf, mouth]))), "coast": enc(lines(coast, 3)), "kumano_angle": round(math.degrees(math.atan2(-(b.y - a.y), b.x - a.x)), 1),
            "koyazaka": {"bearing": round((math.degrees(math.atan2(dx, dy)) + 360) % 360), "dist_m": round(oji.distance(koya))},
            "m": {"hay_asuka": round(hay.distance(asuka)), "asuka_oji": round(asuka.distance(oji)), "foot_hay": round(foot_pt.distance(hay)),
                  "mif_hay_river": round(s_hay - s_mif), "ichida_len": round(ichida.length), "conf_mouth": round(conf.distance(mouth)),
                  "conf_to_water": round(conf.distance(water), 1),
                  "hay_mouth_river": round(s_mouth - s_hay)}}


def relabel_runs(runs, st):
    """The transect's land-use runs as step 3 wrote them, with the stretch through the 出雲大社新宮教会's grounds
    (which step 3 first counted as the shrine's precinct) given its own class."""
    ways, _ = _osm(); izu = _poly(ways[IZUMO_GROUND]); tr = LineString(st["transect"])
    return [[a, b, "izumo" if c == "precinct" and izu.contains(tr.interpolate((a + b) / 2)) else c] for a, b, c in runs]
