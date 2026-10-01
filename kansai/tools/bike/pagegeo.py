"""Page geometry shared by the exporters: JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674) metres to page units
(1 = 100 m) with the main map's origin, and compact SVG path strings."""
from pyproj import Transformer
TR = Transformer.from_crs(4326, 6674, always_xy=True).transform
O = (-69782.048, -171691.754)
def pgm(x, y): return ((x - O[0]) / 100.0, (O[1] - y) / 100.0)
def pg(lon, lat): return pgm(*TR(lon, lat))
def fm(v, nd=1):
    s = (("%." + str(nd) + "f") % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s
def d_of(lines, nd=1):
    out = []
    for l in lines:
        q = [(round(x, nd), round(y, nd)) for x, y in l]
        q = [q[0]] + [b for a, b in zip(q, q[1:]) if b != a]
        if len(q) < 2: continue
        s = "M" + fm(q[0][0], nd) + " " + fm(q[0][1], nd)
        for a, b in zip(q, q[1:]):
            dx, dy = fm(b[0] - a[0], nd), fm(b[1] - a[1], nd)
            s += "l" + dx + ("" if dy.startswith("-") else " ") + dy
        out.append(s)
    return "".join(out)
def simp(pts, tol):
    from shapely.geometry import LineString
    return list(LineString(pts).simplify(tol).coords) if len(pts) > 2 else pts
