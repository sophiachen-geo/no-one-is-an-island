"""Per-corridor metrics. Heights: GSI DEM (5A>5B>5C>10B) on the OSM line every 20 m; inside OSM tunnels and
bridges the height is interpolated between the two ends; then a Hampel filter (window +-3 samples, 3 scaled
MADs) removes isolated spikes from lateral misfit on steep slopes. Climb uses a 5 m hysteresis; the
sensitivity range is (Hampel, 10 m) .. (unfiltered, 2 m)."""
import json, math, statistics as stt, collections
import dem
from route import hav
STEP = 20.0
def hampel(h, k=3, t=3.0):
    out = list(h); n = len(h)
    for i in range(n):
        w = h[max(0, i - k): i + k + 1]
        m = stt.median(w); mad = 1.4826 * stt.median([abs(x - m) for x in w])
        if mad > 0 and abs(h[i] - m) > t * mad: out[i] = m
    return out
def climb(h, hys):
    f = [h[0]]
    for x in h[1:]:
        if abs(x - f[-1]) >= hys: f.append(x)
    if f[-1] != h[-1]: f.append(h[-1])
    up = sum(max(0, b - a) for a, b in zip(f, f[1:])); dn = sum(max(0, a - b) for a, b in zip(f, f[1:]))
    return up, dn
def structure(t):
    if t.get("tunnel") and t.get("tunnel") != "no": return "tunnel"
    if t.get("bridge") and t.get("bridge") != "no": return "bridge"
    return ""
def densify(G, chain):
    pts = []; cum = 0.0
    for a, b in zip(chain, chain[1:]):
        w = None
        for v, L, ww, i in G.adj[a]:
            if v == b: w = ww; break
        if w is None:
            for v, L, ww, i in G.adj[b]:
                if v == a: w = ww; break
        pa, pb = G.xy[a], G.xy[b]; L = hav(pa, pb); n = max(1, int(math.ceil(L / STEP)))
        for k in range(n):
            f = k / n; pts.append((pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f, cum + L * f, w))
        cum += L
    pts.append((G.xy[chain[-1]][0], G.xy[chain[-1]][1], cum, pts[-1][3]))
    return pts
def heights(G, pts):
    raw = []; src = collections.Counter()
    for p in pts:
        h, s = dem.sample(p[0], p[1]); raw.append(h); src[s] += 1
    kind = [structure(G.ways[p[3]].get("tags", {})) for p in pts]
    fx = list(raw); n = len(pts); i = 0
    while i < n:
        if kind[i] or fx[i] is None:
            j = i
            while j < n and (kind[j] or fx[j] is None): j += 1
            a, b = i - 1, (j if j < n else None)
            ha = fx[a] if a >= 0 else None; hb = fx[b] if b is not None else None
            for k in range(i, j):
                if ha is not None and hb is not None:
                    fx[k] = ha + (hb - ha) * (pts[k][2] - pts[a][2]) / max(1e-9, pts[b][2] - pts[a][2])
                else: fx[k] = ha if ha is not None else hb
            i = j
        else: i += 1
    return raw, fx, roadbed(pts, fx, kind), kind, src
def roadbed(pts, fx, kind):
    """Viterbi road-bed tracking (benchdp) on open-road runs; structures re-interpolated between the new ends."""
    import numpy as np, benchdp as B
    n = len(pts); hb = list(fx)
    i = 0
    while i < n:
        if kind[i]: i += 1; continue
        j = i
        while j < n and not kind[j]: j += 1
        if j - i >= 3:
            H = B.grid(pts[i:j]); h, o = B.track(pts[i:j], H)
            for k in range(i, j):
                if not np.isnan(h[k - i]): hb[k] = float(h[k - i])
        i = j
    i = 0
    while i < n:
        if kind[i]:
            j = i
            while j < n and kind[j]: j += 1
            a, b = i - 1, (j if j < n else None)
            for k in range(i, j):
                if a >= 0 and b is not None: hb[k] = hb[a] + (hb[b] - hb[a]) * (pts[k][2] - pts[a][2]) / (pts[b][2] - pts[a][2])
            i = j
        else: i += 1
    return hb
def grade_max(pts, h, win=200.0):
    best = (0, None); j = 0
    for i in range(len(pts)):
        while j < len(pts) and pts[j][2] - pts[i][2] < win: j += 1
        if j >= len(pts): break
        g = (h[j] - h[i]) / (pts[j][2] - pts[i][2]) * 100
        if abs(g) > abs(best[0]): best = (g, pts[i][2])
    return best
def structures(G, pts, kind):
    runs = []
    for p, k in zip(pts, kind):
        if not k: 
            if runs and runs[-1].get("open"): runs[-1]["open"] = False
            continue
        t = G.ways[p[3]].get("tags", {})
        nm = t.get("tunnel:name") or t.get("bridge:name") or (t.get("name") if k == "bridge" and "橋" in (t.get("name") or "") else None) or (t.get("name") if k == "tunnel" and "トンネル" in (t.get("name") or "") else None)
        if runs and runs[-1].get("open") and runs[-1]["kind"] == k:
            runs[-1]["end"] = p[2]
            if nm and not runs[-1]["name"]: runs[-1]["name"] = nm
        else:
            runs.append({"kind": k, "start": p[2], "end": p[2], "name": nm, "open": True, "lonlat": (p[0], p[1])})
    for r in runs:
        r.pop("open", None); r["len"] = round(r["end"] - r["start"] + STEP)
    return runs
