"""Elevation profile and ride statistics for a routed path.
- Densify the path every STEP m; sample GSI DEM (dem.sample: DEM5A > 5B > 5C > DEM10B).
- Tunnels and bridges: the DEM shows the hill above a tunnel and the valley under a bridge, so inside every
  OSM tunnel=* / bridge=* run the height is interpolated linearly between the two ends (portals / abutments).
- Climb: total ascent with a hysteresis of HYS m (a rise counts only once it exceeds HYS from the last
  low), the usual way to keep DEM noise out of the sum; also reported without hysteresis for transparency.
- Gradients over a sliding 200 m window."""
import math, collections
import dem
from route import hav
STEP = 20.0
HYS = 3.0
def densify(G, edges):
    """Return list of (lon, lat, cum_m, way_id) every STEP m along the edges."""
    out = []; cum = 0.0
    for u, v, w, L in edges:
        a, b = G.xy[u], G.xy[v]
        n = max(1, int(math.ceil(L / STEP)))
        for k in range(n):
            f = k / n
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, cum + L * f, w))
        cum += L
    lastv = edges[-1][1]
    out.append((G.xy[lastv][0], G.xy[lastv][1], cum, edges[-1][2]))
    return out
def structure(t):
    if t.get("tunnel") in ("yes", "building_passage", "culvert", "avalanche_protector") or t.get("covered") == "yes" and t.get("tunnel"):
        return "tunnel"
    if t.get("bridge") and t.get("bridge") != "no":
        return "bridge"
    return ""
def profile(G, edges):
    pts = densify(G, edges)
    hs = []; srcs = collections.Counter()
    for lon, lat, c, w in pts:
        h, s = dem.sample(lon, lat); hs.append(h); srcs[s] += 1
    kind = [structure(G.ways[w].get("tags", {})) for *_, w in pts]
    # interpolate across structure runs (and any DEM gaps)
    n = len(pts); i = 0
    fixed = list(hs)
    while i < n:
        if kind[i] or fixed[i] is None:
            j = i
            while j < n and (kind[j] or fixed[j] is None): j += 1
            a = i - 1; b = j if j < n else None
            ha = fixed[a] if a >= 0 else None; hb = fixed[b] if b is not None else None
            for k in range(i, j):
                if ha is not None and hb is not None:
                    f = (pts[k][2] - pts[a][2]) / max(1e-9, pts[b][2] - pts[a][2]); fixed[k] = ha + (hb - ha) * f
                else:
                    fixed[k] = ha if ha is not None else hb
            i = j
        else:
            i += 1
    return pts, fixed, kind, srcs
def climb(h, hys=HYS):
    """Total ascent/descent after a hysteresis filter: a height is kept only once it differs by >= hys
    from the last kept height (hys = 0 gives the raw sum)."""
    f = [h[0]]
    for x in h[1:]:
        if abs(x - f[-1]) >= hys: f.append(x)
    if f[-1] != h[-1]: f.append(h[-1])
    up = sum(max(0, b - a) for a, b in zip(f, f[1:])); down = sum(max(0, a - b) for a, b in zip(f, f[1:]))
    return up, down
def grades(pts, h, win=200.0):
    out = []
    j = 0
    for i in range(len(pts)):
        while j < len(pts) and pts[j][2] - pts[i][2] < win: j += 1
        if j >= len(pts): break
        out.append((pts[i][2], (h[j] - h[i]) / (pts[j][2] - pts[i][2]) * 100))
    return out
def stats(G, edges):
    pts, h, kind, srcs = profile(G, edges)
    L = pts[-1][2]
    up, down = climb(h); up0, down0 = climb(h, 0.0)
    gr = grades(pts, h)
    # structures (by way, merged consecutively)
    runs = []
    for (lon, lat, c, w), k in zip(pts, kind):
        if k:
            if runs and runs[-1]["kind"] == k and runs[-1]["way_name"] == (G.ways[w].get("tags", {}).get("name") or G.ways[w].get("tags", {}).get("tunnel:name") or G.ways[w].get("tags", {}).get("bridge:name") or str(w)) and c - runs[-1]["end"] <= STEP * 1.5:
                runs[-1]["end"] = c
            else:
                t = G.ways[w].get("tags", {})
                runs.append({"kind": k, "start": c, "end": c, "way_name": t.get("name") or t.get("tunnel:name") or t.get("bridge:name") or str(w), "tunnel_name": t.get("tunnel:name"), "bridge_name": t.get("bridge:name"), "way": w})
    for r in runs: r["len"] = r["end"] - r["start"] + STEP
    # road composition
    comp = collections.Counter(); refs = collections.Counter(); surf = collections.Counter()
    for u, v, w, Le in edges:
        t = G.ways[w].get("tags", {})
        comp[t.get("highway")] += Le
        refs[t.get("ref") or t.get("name") or "(unnamed " + t.get("highway", "") + ")"] += Le
        s = t.get("surface") or ("unknown(track)" if t.get("highway") == "track" else "unknown")
        surf[s] += Le
    return {"len_m": L, "up_m": up, "down_m": down, "up_raw_m": up0, "down_raw_m": down0,
            "h_start": h[0], "h_end": h[-1], "h_max": max(h), "h_min": min(h),
            "max_grade_200m": max(g for c, g in gr) if gr else None, "min_grade_200m": min(g for c, g in gr) if gr else None,
            "structures": runs, "composition": dict(comp), "refs": refs.most_common(12), "surface": dict(surf),
            "dem_sources": dict(srcs)}, pts, h
