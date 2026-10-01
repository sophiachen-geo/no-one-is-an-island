import json, sys, numpy as np
from route import Graph, hav
import metrics as M, benchdp as B, gsi_pts
roads = json.load(open("roads.json")); G = Graph(roads)
C = json.load(open("chains.json")); CO = {r["id"]: r for r in json.load(open("corridors.json"))}
for cid in map(int, sys.argv[1:]):
    ch = C["chains"][cid]
    pts = M.densify(G, ch)
    raw, fx, hp, kind, src = M.heights(G, pts)
    H = B.grid(pts)
    # run DP on open-road runs only
    hb = np.array(fx, dtype=float); offs = np.zeros(len(pts))
    i = 0; n = len(pts)
    while i < n:
        if kind[i]: i += 1; continue
        j = i
        while j < n and not kind[j]: j += 1
        if j - i >= 3:
            h, o = B.track(pts[i:j], H[i:j]); hb[i:j] = h; offs[i:j] = o
        i = j
    # re-interpolate across structures using DP ends
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
    up5 = M.climb(list(hb), 5); up2 = M.climb(list(hb), 2); up10 = M.climb(list(hb), 10)
    g = M.grade_max(pts, list(hb))
    print(f"c{cid} {pts[-1][2]/1000:.1f} km | raw-hampel up5 {CO[cid]['up5']} gmax {CO[cid]['gmax'][0]} | DP up5 {[round(x) for x in up5]} up2 {[round(x) for x in up2]} up10 {[round(x) for x in up10]} gmax {g[0]:.1f}% @ {g[1]:.0f} m | |off| mean {np.mean(np.abs(offs)):.1f} m, >10 m {np.mean(np.abs(offs) > 10)*100:.0f}% | max h {hb.max():.0f}")
    # benchmarks
    tiles = sorted({gsi_pts.tile_of(p[0], p[1]) for p in pts}); gp = gsi_pts.points_in_tiles(tiles)
    errs = []
    for lon, lat, alt, kd in gp:
        k = min(range(n), key=lambda q: (pts[q][0] - lon) ** 2 + ((pts[q][1] - lat) * 1.2) ** 2)
        if hav((pts[k][0], pts[k][1]), (lon, lat)) <= 15 and not kind[k]:
            errs.append((kd[:5], alt, round(raw[k], 1) if raw[k] is not None else None, round(float(hb[k]), 1)))
    print("   benchmarks:", errs[:8])
    json.dump({"cum": [p[2] for p in pts], "raw": [x if x is None else round(x, 1) for x in raw], "dp": [round(float(x), 1) for x in hb], "off": [float(x) for x in offs]}, open(f"dp_c{cid}.json", "w"))
