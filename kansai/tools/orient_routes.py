"""Orient the pilgrimage routes the pilgrims' way, so that their moving dashes run toward the shrines.

A sub-path of a layer below is reversed when its start lies nearer the layer's goal than its end: for the Kumano Kodō,
the nearest of the three shrines (Hongū, Hayatama, Nachi); for the river route from Hongū to Hayatama, the river mouth
(downstream). The geometry does not change. The page animates these layers' dashes from the start of each line to its end.
09_inject.py calls orient() before it writes the page. Run alone, it orients the GEO block of a page in place:

    python3 orient_routes.py [path/to/kansai/index.html]
"""
import json, math, os, re, sys

SHRINES = ("hongu", "hayatama", "nachi")
GOALS = {"kodo": SHRINES, "kodo_iseji": SHRINES, "kodo_routed": SHRINES, "river_route": ("kumano_mouth",)}   # layer → points in g["pts"]
SUB = re.compile(r"M[^M]*")
NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")


def fnum(v):   # as in 07_build.py and 16_extras.py
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    if s.startswith("0."): s = s[1:]
    elif s.startswith("-0."): s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s


def decode(sub, k):   # "Mx yl dx dy ..." → absolute points in integer units of 1/k
    head, _, body = sub[1:].partition("l")
    x, y = (round(float(v) * k) for v in NUM.findall(head))
    pts = [(x, y)]
    vals = [round(float(v) * k) for v in NUM.findall(body)]
    for dx, dy in zip(vals[0::2], vals[1::2]):
        x += dx; y += dy; pts.append((x, y))
    return pts


def encode(pts, k):   # the generators' ring_d() on points already rounded
    parts = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        a, b = fnum((bx - ax) / k), fnum((by - ay) / k)
        parts.append(a + ("" if b.startswith("-") else " ") + b)
    return "M" + fnum(pts[0][0] / k) + " " + fnum(pts[0][1] / k) + "l" + " ".join(parts).replace(" -", "-")


def orient(g, goals=GOALS):
    """Reverse, in g["layers"], every sub-path that runs away from its layer's goal; returns {layer: n reversed}."""
    done = {}
    for name, targets in goals.items():
        goal = [g["pts"][t] for t in targets]
        def near(p, k): return min(math.hypot(p[0] / k - a, p[1] / k - b) for a, b in goal)
        d = g["layers"].get(name) or ""
        decimals = max((len(t.partition(".")[2]) for t in NUM.findall(d)), default=0)
        k = 10 ** decimals
        subs, n = [], 0
        for sub in SUB.findall(d):
            pts = decode(sub, k)
            assert encode(pts, k) == sub, (name, sub[:60])   # the decoder reads exactly what the generators wrote
            if near(pts[0], k) < near(pts[-1], k):
                rev = encode(pts[::-1], k)
                assert decode(rev, k) == pts[::-1]
                subs.append(rev); n += 1
            else:
                subs.append(sub)
        g["layers"][name] = "".join(subs)
        done[name] = n
    return done


if __name__ == "__main__":
    page = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html")
    html = open(page, encoding="utf-8").read()
    m = re.search(r"/\*GEO:BEGIN\*/(.*?)/\*GEO:END\*/", html, re.S)
    g = json.loads(m.group(1))
    assert json.dumps(g, ensure_ascii=False, separators=(",", ":")) == m.group(1), "the GEO block does not round-trip; run 09_inject.py"
    done = orient(g)
    for name, n in done.items(): print(f"{name:12s} {n} sub-path(s) reversed")
    blob = json.dumps(g, ensure_ascii=False, separators=(",", ":"))
    open(page, "w", encoding="utf-8").write(html[:m.start(1)] + blob + html[m.end(1):])
