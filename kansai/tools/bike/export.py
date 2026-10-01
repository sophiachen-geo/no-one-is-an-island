"""Write bike.js (window.__BIKE) for the page: corridors in page units (1 = 100 m, JGD2011 / CS VI),
their metrics and road-bed profiles, nodes, route options per pair of shrines, and the motorways bicycles may
not use. Page = ((E - O0)/100, (O1 - N)/100), O = (-69782.048, -171691.754) as everywhere on the page."""
import json, math, collections, sys
from pyproj import Transformer
from route import Graph, hav
TR = Transformer.from_crs(4326, 6674, always_xy=True)
O = (-69782.048, -171691.754)
def pg(lon, lat):
    x, y = TR.transform(lon, lat); return ((x - O[0]) / 100.0, (O[1] - y) / 100.0)
def fm(v):
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s
def d_of(lines):
    out = []
    for l in lines:
        q = [(round(x, 1), round(y, 1)) for x, y in l]
        q = [q[0]] + [b for a, b in zip(q, q[1:]) if b != a]
        s = "M" + fm(q[0][0]) + " " + fm(q[0][1])
        for a, b in zip(q, q[1:]):
            dx, dy = fm(b[0] - a[0]), fm(b[1] - a[1])
            s += "l" + dx + ("" if dy.startswith("-") else " ") + dy
        out.append(s)
    return "".join(out)
def simplify(ll, tol=0.05):
    """Douglas-Peucker in page units (tol 0.05 = 5 m)."""
    from shapely.geometry import LineString
    return list(LineString(ll).simplify(tol, preserve_topology=False).coords)
