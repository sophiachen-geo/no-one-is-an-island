"""Fast even-odd point-in-polygon for the page's SVG path layers (1 unit = 100 m).

Edges are bucketed by y so that testing tens of thousands of points against a detailed hazard layer takes
seconds in pure Python. Used by the build (tools/17_round3.py) and by the QA gate (run.py), so both count
with exactly the geometry the reader sees.
"""
import math
import re

_TOK = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def rings(d):
    out, cur, x, y, cmd, sx, sy = [], [], 0.0, 0.0, None, 0.0, 0.0
    toks = _TOK.findall(d)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                if cur: out.append(cur); cur = []
                x, y = sx, sy
            continue
        if cmd in ("M", "m"):
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "m": nx += x; ny += y
            if cur: out.append(cur)
            cur = [(nx, ny)]; x, y, sx, sy = nx, ny, nx, ny
            cmd = "L" if cmd == "M" else "l"
        elif cmd in ("L", "l"):
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "l": nx += x; ny += y
            x, y = nx, ny; cur.append((x, y))
        elif cmd in ("H", "h"):
            v = float(toks[i]); i += 1
            x = v if cmd == "H" else x + v; cur.append((x, y))
        elif cmd in ("V", "v"):
            v = float(toks[i]); i += 1
            y = v if cmd == "V" else y + v; cur.append((x, y))
        else:
            raise ValueError(f"unsupported path command {cmd!r}")
    if cur: out.append(cur)
    return out


class Region:
    """Even-odd fill of one or more path strings (the way SVG draws them)."""

    def __init__(self, *paths, bin_size=0.5):
        self.b = bin_size
        self.bins = {}
        for d in paths:
            for r in rings(d):
                for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
                    if y1 == y2: continue
                    lo, hi = min(y1, y2), max(y1, y2)
                    for k in range(math.floor(lo / bin_size), math.floor(hi / bin_size) + 1):
                        self.bins.setdefault(k, []).append((x1, y1, x2, y2))

    def contains(self, x, y):
        c = False
        for x1, y1, x2, y2 in self.bins.get(math.floor(y / self.b), ()):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c
