"""Minimal parser for MoJ 地図XML (登記所備付地図データ).

Builds 筆 polygons in the file's plane coordinates.
MoJ convention: zmn:X = northing, zmn:Y = easting (metres).
"""
from lxml import etree
from shapely.geometry import Polygon
from shapely.validation import make_valid

NS = {"t": "http://www.moj.go.jp/MINJI/tizuxml",
      "z": "http://www.moj.go.jp/MINJI/tizuzumen"}
Z = "{http://www.moj.go.jp/MINJI/tizuzumen}"
T = "{http://www.moj.go.jp/MINJI/tizuxml}"


def _txt(el, tag):
    c = el.find(T + tag)
    return c.text.strip() if c is not None and c.text else None


def parse(data: bytes):
    root = etree.fromstring(data, parser=etree.XMLParser(huge_tree=True))
    meta = {k: _txt(root, k) for k in ("地図名", "市区町村コード", "市区町村名", "座標系", "測地系判別")}
    sp = root.find(T + "空間属性")

    # points: id -> (E, N)
    pts = {}
    for p in sp.iterfind(Z + "GM_Point"):
        dp = p.find(f"{Z}GM_Point.position/{Z}DirectPosition")
        n = float(dp.find(Z + "X").text); e = float(dp.find(Z + "Y").text)
        pts[p.get("id")] = (e, n)

    # curves: id -> list of (E, N), honouring orientation
    curves = {}
    for c in sp.iterfind(Z + "GM_Curve"):
        seq = []
        for col in c.iter(Z + "GM_PointArray.column"):
            ind = col.find(f"{Z}GM_Position.indirect/{Z}GM_PointRef.point")
            if ind is not None:
                seq.append(pts[ind.get("idref")])
            else:
                d = col.find(Z + "GM_Position.direct")
                seq.append((float(d.find(Z + "Y").text), float(d.find(Z + "X").text)))
        o = c.find(Z + "GM_OrientablePrimitive.orientation")
        if o is not None and o.text and o.text.strip() == "-":
            seq = seq[::-1]
        curves[c.get("id")] = seq

    stats = {"ring_gaps": 0, "rings": 0}

    def ring_coords(ring_el):
        out = []
        for g in ring_el.iterfind(Z + "GM_CompositeCurve.generator"):
            seg = curves[g.get("idref")]
            if not out:
                out.extend(seg)
                continue
            if out[-1] == seg[0]:
                out.extend(seg[1:])
            elif out[-1] == seg[-1]:
                out.extend(seg[::-1][1:])
            elif len(out) == len(curves[ring_el.find(Z + "GM_CompositeCurve.generator").get("idref")]) and out[0] in (seg[0], seg[-1]):
                # first segment was stored in the other direction
                out.reverse()
                out.extend(seg[1:] if out[-1] == seg[0] else seg[::-1][1:])
            else:
                stats["ring_gaps"] += 1
                out.extend(seg)
        stats["rings"] += 1
        if out and out[0] != out[-1]:
            out.append(out[0])
        return out

    surfaces = {}
    for s in sp.iterfind(Z + "GM_Surface"):
        polys = []
        for pg in s.iter(Z + "GM_Polygon"):
            sb = pg.find(f"{Z}GM_Polygon.boundary/{Z}GM_SurfaceBoundary")
            ext = sb.find(f"{Z}GM_SurfaceBoundary.exterior/{Z}GM_Ring")
            ints = [ring_coords(r) for r in sb.iterfind(f"{Z}GM_SurfaceBoundary.interior/{Z}GM_Ring")]
            polys.append(Polygon(ring_coords(ext), ints))
        surfaces[s.get("id")] = polys

    th = root.find(T + "主題属性")
    fude = []
    for f in th.iterfind(T + "筆"):
        shape = f.find(T + "形状")
        polys = surfaces.get(shape.get("idref")) if shape is not None else None
        if not polys:
            continue
        geom = polys[0] if len(polys) == 1 else polys[0].union(polys[1:])
        if not geom.is_valid:
            geom = make_valid(geom)
        rec = {"id": f.get("id")}
        for k in ("大字コード", "丁目コード", "小字コード", "予備コード", "大字名", "丁目名",
                  "小字名", "予備名", "地番", "精度区分", "座標値種別"):
            rec[k] = _txt(f, k)
        comp = []
        for m in f.iterfind(T + "筆界未定構成筆"):
            comp.append("".join(filter(None, [_txt(m, "大字名"), _txt(m, "丁目名"), _txt(m, "小字名")])) + (_txt(m, "地番") or ""))
        rec["筆界未定構成筆"] = comp or None
        fude.append((rec, geom))
    return meta, fude, stats
