"""Kamikura micro-study, step 8: is the terrain the neighbourhood's hidden geometric generator? Measure it.

Reads foot.json (06), parcels.json (07), study.json (03), terrain.npz (02), osm.json, GSI optimal vector tiles.
Writes align.json and walls.json (the retaining walls found in the 1 m DEM).

References
  foot   the consensus foot of step 6, lightly smoothed (running median of 5 profiles, then a 22 m running mean);
         its local direction is taken over ±10 m.
  grid   the town grid: the dominant direction (axial, period 90°) of GSI road edges more than 100 m east of the
         foot, within 300 m north and south of the study area.

Feature classes (all in JGD2011 / CS VI metres)
  channel     centre line of the drainage channel (GSI water area, step 3)
  banks       its banks: GSI water edges (5201/5203)
  legal_water the cadastre's waterway parcels (水), registered in step 7
  backs       back boundaries of numbered parcels (kind "private" in parcels.json: a lot with a 地番, whoever owns it):
              the edges farthest from each parcel's street frontage
  temple      the property of 妙心寺 and 宗応寺 (the parcels under each temple), the shrine's lower precinct and,
              beside it, the grounds of the 出雲大社新宮教会 (OSM ways 500803106, 500803107): religious grounds
  lanes       OSM lanes, paths, steps and residential streets (not the national or prefectural roads)
  walls       retaining walls and cut faces found in DEM1A: ground stepping ≥ 1 m at ≥ 45° over 1 m, outside
              buildings (GSI outlines + 1.5 m) and the channel (+ 2 m), at least 4 m long
  buildings   long axis of each GSI building (minimum rotated rectangle)

Test: every feature is cut into pieces of at most 10 m (shared parcel boundaries counted once). A piece is counted
only where the local foot direction and the grid differ by at least 10° (elsewhere the two cannot be told apart); it
"follows the foot" when its direction is closer to the foot's than to the grid's (axial, period 90°: parallel or
square to either). Statistic: the length-weighted share of such pieces that follow the foot (buildings: weighted by
footprint area). Chance = circular shift: the foot's sequence of local directions is slid along the foot by every
offset of at least 50 m (wrapping round at the ends) and the statistic recomputed, so that the foot's bends meet
features they did not shape while both keep their own spatial pattern; one-sided p. Pieces of one line or one
neighbourhood are not independent, and shuffling single pieces (kept as p_perm for the record) makes p far too
small. As a check, p_100 repeats the shift test with a minimum offset of 100 m; a run counts as significant on the
page only when it passes both (robust.significant_both). n_units counts the distinct lines
(or buildings) among the counted pieces. For the long single lines (channel, banks, legal water) a second measure is
whether they copy the foot's bends: correlation of their east–west wiggles with the foot's over the stretch where
they run within 40 m.
"""
import json, math, os, sys
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, LineString, Point, box, MultiLineString
from shapely.ops import unary_union
from shapely import STRtree
from skimage import morphology, measure
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsi import tiles_layers                                   # noqa: E402

LL2P = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
BANDS = [(0, 25), (25, 50), (50, 100), (100, 200)]
WALL_BANDS = [(-15, 0)] + BANDS
TEMPLES = {"妙心寺": (135.984329, 33.724781), "宗応寺": (135.984268, 33.725773)}
ANCHOR_PARCEL = ("千穂", "１丁目", "715-3")                     # the school's parcel, step 7's anchor


def is_school(p): return (p["oaza"], p["chome"], p["chiban"]) == ANCHOR_PARCEL
SHRINE_WAYS = [500803106, 500803107]          # the shrine's lower precinct and the 出雲大社新宮教会's grounds beside it
LANE_KINDS = {"residential", "unclassified", "service", "living_street", "path", "footway", "steps", "pedestrian", "track"}
PIECE = 10.0
SHIFT_MIN, SHIFT_CHECK = 25, 50                                 # profiles (2 m apart): 50 m, and 100 m as a check
rng = np.random.default_rng(6674)


def adiff(a, b, period=90.0):
    d = np.abs((np.asarray(a) - np.asarray(b)) % period); return np.minimum(d, period - d)


def bearing(dx, dy): return (math.degrees(math.atan2(dx, dy)) + 360) % 180


def axial_mean(angles, w, period):
    k = 360.0 / period; a = np.radians(np.asarray(angles) * k); w = np.asarray(w, float)
    C, S = (w * np.cos(a)).sum() / w.sum(), (w * np.sin(a)).sum() / w.sum()
    return (math.degrees(math.atan2(S, C)) / k) % period, float(math.hypot(C, S))


def run_median(a, n):
    p = n // 2; ap = np.pad(a, p, mode="edge"); return np.array([np.median(ap[i:i + n]) for i in range(len(a))])


def run_mean(a, n):
    p = n // 2; return np.convolve(np.pad(a, p, mode="edge"), np.ones(n) / n, mode="valid")


class Foot:
    def __init__(self, F):
        R = F["profiles"]
        self.y = np.array([r["y"] for r in R]); fx = np.array([r["foot_x"] for r in R]); fy = np.array([r["foot_y"] for r in R])
        self.x_wig = run_median(fx, 5)                           # light smoothing: keeps bends ≥ ~10 m
        self.x = run_mean(self.x_wig, 11); self.yy = run_mean(run_median(fy, 5), 11)
        self.nx = np.array([r["nx"] for r in R]); self.ny = np.array([r["ny"] for r in R])
        k = 5
        self.dir = np.array([bearing(self.x[min(i + k, len(R) - 1)] - self.x[max(i - k, 0)],
                                     self.yy[min(i + k, len(R) - 1)] - self.yy[max(i - k, 0)]) for i in range(len(R))])
        self.line = LineString(np.column_stack([self.x, self.yy]))
        self.tree = cKDTree(np.column_stack([self.x, self.yy]))

    def at(self, P):
        """Nearest foot vertex for each point: signed distance (east/downslope positive) and local foot direction."""
        P = np.atleast_2d(P); dist, i = self.tree.query(P)
        d = (P[:, 0] - self.x[i]) * self.nx[i] + (P[:, 1] - self.yy[i]) * self.ny[i]
        # beyond the ends of the measured front the reference is extrapolated poorly: flag those
        inside = (P[:, 1] <= self.yy.max() + 5) & (P[:, 1] >= self.yy.min() - 5)
        return d, self.dir[i], inside


def pieces(line, maxlen=PIECE, unit=0):
    """Split a line into pieces ≤ maxlen; each piece → (midpoint x, y, direction, length, unit: the source line)."""
    out = []
    for L in getattr(line, "geoms", [line]):
        if L.geom_type != "LineString" or L.length < 0.5: continue
        n = max(1, int(math.ceil(L.length / maxlen)))
        for k in range(n):
            a = L.interpolate(k * L.length / n); b = L.interpolate((k + 1) * L.length / n)
            seg = LineString([a, b]); m = seg.interpolate(0.5, normalized=True)
            # direction of the actual sub-line (not just its end points) — length-weighted axial mean of its edges
            sub = substring(L, k * L.length / n, (k + 1) * L.length / n)
            c = np.asarray(sub.coords); dxy = np.diff(c, axis=0); ln = np.hypot(dxy[:, 0], dxy[:, 1]); ok = ln > 1e-6
            if not ok.any(): continue
            th, _ = axial_mean([bearing(dx, dy) for dx, dy in dxy[ok]], ln[ok], 180)
            out.append((m.x, m.y, th, float(ln[ok].sum()), unit))
    return out


def substring(L, a, b):
    from shapely.ops import substring as ss
    return ss(L, a, b)


def classify(rows, foot, grid, band):
    """rows: (x, y, θ, w, unit). Share following the foot among discriminating pieces, against the circular-shift null."""
    if not rows: return None
    A = np.array([(r[0], r[1], r[2], r[3]) for r in rows]); unit = np.array([r[4] for r in rows])
    d, fdir, inside = foot.at(A[:, :2]); _, idx = foot.tree.query(A[:, :2])
    sel = inside & (d >= band[0]) & (d < band[1])
    th, w = A[:, 2], A[:, 3]
    def stat(fd):
        disc = sel & (adiff(fd, grid) >= 10)
        if disc.sum() < 3: return np.nan
        return float((w[disc] * (adiff(th[disc], fd[disc]) < adiff(th[disc], grid))).sum() / w[disc].sum())
    disc = sel & (adiff(fdir, grid) >= 10)
    tot_len = float(w[sel].sum())
    if disc.sum() < 3: return {"from": band[0], "to": band[1], "length_m": round(tot_len), "n_disc": int(disc.sum())}
    fol = disc & (adiff(th, fdir) < adiff(th, grid))
    obs = stat(fdir); N = len(foot.dir)
    def shifted(kmin):
        T = np.array([stat(foot.dir[(idx + k) % N]) for k in range(kmin, N - kmin + 1)]); return T[~np.isnan(T)]
    def pval(T): return round(float((np.sum(T >= obs - 1e-12) + 1) / (len(T) + 1)), 4)
    T, T100 = shifted(SHIFT_MIN), shifted(SHIFT_CHECK)
    # for the record: the earlier null, foot directions shuffled among the pieces (ignores that pieces cluster)
    fd, wd, thd = fdir[disc], w[disc], th[disc]
    perm = np.array([(wd * (adiff(thd, q) < adiff(thd, grid))).sum() / wd.sum() for q in (rng.permutation(fd) for _ in range(2000))])
    return {"from": band[0], "to": band[1], "length_m": round(tot_len), "n_disc": int(disc.sum()), "disc_len_m": round(float(wd.sum())),
            "n_units": int(len(set(unit[disc]))), "n_units_follow": int(len(set(unit[fol]))),
            "follow_foot_pct": round(100 * obs, 1), "chance_pct": round(100 * float(T.mean()), 1), "p": pval(T), "n_shifts": int(len(T)),
            "p_100": pval(T100), "p_perm": round(float((np.sum(perm >= obs - 1e-12) + 1) / (len(perm) + 1)), 4),
            "within10_foot_pct": round(100 * float((wd * (adiff(thd, fd) <= 10)).sum() / wd.sum()), 1),
            "within10_grid_pct": round(100 * float((wd * (adiff(thd, grid) <= 10)).sum() / wd.sum()), 1)}


def wiggle(line, foot, maxd=40.0, step=2.0):
    """Does a line copy the foot's bends? Over the stretch where it runs within maxd of the foot (east of it),
    correlate its east–west position with the foot's after removing each one's straight trend."""
    ys = np.arange(foot.yy.min() + 10, foot.yy.max() - 10, step)
    fx = np.interp(ys, foot.y[::-1], foot.x_wig[::-1])
    xs = []
    for y in ys:
        h = line.intersection(LineString([(-1e5, y), (1e5, y)]))
        pts = [p for p in getattr(h, "geoms", [h]) if p.geom_type == "Point"]
        xs.append(min((p.x for p in pts), key=lambda v: abs(v - np.interp(y, foot.y[::-1], foot.x[::-1])), default=np.nan))
    xs = np.array(xs); off = xs - fx
    ok = ~np.isnan(xs) & (off >= -5) & (off <= maxd)
    if ok.sum() < 15: return {"n": int(ok.sum())}
    # longest contiguous run
    runs, cur = [], []
    for i, v in enumerate(ok):
        if v: cur.append(i)
        elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    r = max(runs, key=len)
    if len(r) < 15: return {"n": len(r)}
    y_, x_, f_ = ys[r], xs[r], fx[r]
    rx = x_ - np.polyval(np.polyfit(y_, x_, 1), y_); rf = f_ - np.polyval(np.polyfit(y_, f_, 1), y_)
    corr = float(np.corrcoef(rx, rf)[0, 1]) if rf.std() > 0 and rx.std() > 0 else float("nan")
    return {"n": len(r), "stretch_m": round(float(y_.max() - y_.min()), 1), "y_from": round(float(y_.max()), 1), "y_to": round(float(y_.min()), 1),
            "offset_mean_m": round(float((x_ - f_).mean()), 1), "offset_sd_m": round(float((x_ - f_).std()), 2),
            "foot_wiggle_sd_m": round(float(rf.std()), 2), "line_wiggle_sd_m": round(float(rx.std()), 2), "wiggle_r": round(corr, 2)}


def row_offsets(geom, foot, mode, step=2.0):
    """East–west position relative to the foot on rows every `step` m: for areas the midpoint of the chord nearest
    the foot ('area'), for lines the crossing nearest the foot but at least 3 m east of it ('line'), for the west
    edge of an area ('west'). Returns rows (y, offset)."""
    out = []
    for y in np.arange(foot.yy.max() - 2, foot.yy.min() + 2, -step):
        fx = float(np.interp(y, foot.yy[::-1], foot.x[::-1]))
        h = geom.intersection(LineString([(fx - 200, y), (fx + 600, y)]))
        parts = [g for g in getattr(h, "geoms", [h]) if not g.is_empty]
        if not parts: continue
        if mode == "area":
            xs = [(g.bounds[0] + g.bounds[2]) / 2 for g in parts if g.geom_type == "LineString"]
        elif mode == "west":
            xs = [min(g.bounds[0] for g in parts)]
        else:
            xs = [g.x for g in parts if g.geom_type == "Point" and g.x >= fx + 3]
        if xs: out.append((float(y), float(min(xs, key=lambda v: abs(v - fx)) - fx)))
    return out


def summarise_offsets(rows):
    if not rows: return None
    o = np.array([r[1] for r in rows]); y = np.array([r[0] for r in rows])
    return {"rows": len(rows), "y_north": round(float(y.max()), 1), "y_south": round(float(y.min()), 1),
            "median_m": round(float(np.median(o)), 1), "p25_m": round(float(np.percentile(o, 25)), 1),
            "p75_m": round(float(np.percentile(o, 75)), 1)}


def channel_courses(st, parcels, key):
    """Today's channel against the cadastre, in 4 m pieces: the longest unbroken run of pieces bearing 25–65° is the
    diagonal reach that crosses from the grid to the foot; north and south of it are the other two. For each reach
    the share of length inside the unnumbered road and waterway strips (道, 水, 長狭物), inside numbered parcels (地番:
    the drawing records lots, not owners) and more than 3 m inside them (beyond the registration's error), inside the
    school's parcel (715-3), and within 3 m of a waterway parcel."""
    ch = LineString(st["ichida"])
    def U(kinds): return unary_union([Polygon(p[key][0]).buffer(0) for p in parcels if p["kind"] in kinds and p[key]])
    pub, water = U(("road", "water", "strip")), U(("water",))
    num = [Polygon(p[key][0]).buffer(0) for p in parcels if p["kind"] == "private" and p[key]]
    school = unary_union([Polygon(p[key][0]).buffer(0) for p in parcels if is_school(p) and p[key]])
    cover = U(("private", "road", "water", "strip", "other"))
    # measure on the line itself: cut it at the first and last diagonal piece
    P = [(x, y, th, w) for x, y, th, w, _ in pieces(ch.intersection(cover.buffer(2)), 4.0)]
    flag = [25 <= q[2] <= 65 for q in P]
    out = {}
    runs, start = [], None                                     # the longest unbroken diagonal run is the crossing reach
    for i, f in enumerate(flag + [False]):
        if f and start is None: start = i
        if not f and start is not None: runs.append((start, i - 1)); start = None
    if not runs: return out
    i0, i1 = max(runs, key=lambda r: r[1] - r[0])
    parts = {"north": P[:i0], "diagonal": P[i0:i1 + 1], "south": P[i1 + 1:]}
    for k, ps in parts.items():
        L_ = sum(q[3] for q in ps)
        if not L_: continue
        pts = [Point(q[0], q[1]) for q in ps]; w = np.array([q[3] for q in ps])
        def share(test):
            return round(100 * float(sum(wi for wi, pt in zip(w, pts) if test(pt)) / L_), 1)
        def depth(pt):                                      # how far inside the numbered parcel that holds it
            return next((g.exterior.distance(pt) for g in num if g.contains(pt)), None)
        wb = water.buffer(3.0)
        out[k] = {"length_m": round(L_), "public_pct": share(pub.contains),
                  "numbered_pct": share(lambda pt: depth(pt) is not None),
                  "numbered_deep_pct": share(lambda pt: (depth(pt) or 0) > 3.0),
                  "school_pct": share(school.contains), "school_deep_m": round(max([school.exterior.distance(pt) for pt in pts if school.contains(pt)], default=0.0), 1),
                  "near_water_pct": share(wb.contains)}
    return out


def back_edges(parcels, foot):
    """Back boundaries: for each numbered parcel with a street frontage — an edge facing a road or waterway parcel
    (道, 水, 長狭物; the cadastre maps them as parcels of their own) — the edges whose midpoints lie beyond 60 % of
    the parcel's depth measured from that frontage. Edges on the sheet's outer limit (the mountain side, where the
    drawings end) count as backs, never as frontage."""
    priv = [Polygon(p["rings"][0]) for p in parcels if p["kind"] == "private" and p["rings"]]
    pub = [Polygon(p["rings"][0]).buffer(0) for p in parcels if p["kind"] in ("road", "water", "strip") and p["rings"]]
    ptree = STRtree(pub)
    out, fronts = [], []
    for P in priv:
        P = P.simplify(0.4)
        c = np.asarray(P.exterior.coords)
        edges = [LineString([c[i], c[i + 1]]) for i in range(len(c) - 1) if math.dist(c[i], c[i + 1]) >= 1.0]
        front, other = [], []
        for e in edges:
            m = e.interpolate(0.5, normalized=True); dx, dy = np.subtract(e.coords[1], e.coords[0]); L = math.hypot(dx, dy)
            nx, ny = dy / L, -dx / L
            q = Point(m.x + nx * 1.2, m.y + ny * 1.2)
            if P.contains(q): q = Point(m.x - nx * 1.2, m.y - ny * 1.2)
            (front if any(pub[j].contains(q) for j in ptree.query(q)) else other).append(e)
        if not front or not other: continue
        f = max(front, key=lambda e: e.length); fronts.append(f)
        depth = max(Point(v).distance(f) for v in c)
        if depth < 4: continue
        for e in other:
            m = e.interpolate(0.5, normalized=True)
            if m.distance(f) >= 0.6 * depth and e.length >= 2.0: out.append(e)
    # a boundary shared by two parcels (back to back, or one's back the other's side) is one line on the ground
    def dedupe(E):
        seen, keep = set(), []
        for e in E:
            k = tuple(sorted(tuple(round(v, 1) for v in c) for c in e.coords))
            if k not in seen: seen.add(k); keep.append(e)
        return keep
    return dedupe(out), dedupe(fronts)


def dem_walls(z, x0, y1, W, H, exclude, foot, ys):
    """Steps ≥ 1 m at ≥ 45° over 1 m in bare ground, outside the excluded areas → skeleton lines."""
    zf = np.where(np.isnan(z), np.nanmedian(z), z)
    gy, gx = np.gradient(zf); slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    rng3 = ndi.maximum_filter(zf, 3) - ndi.minimum_filter(zf, 3)
    m = (slope >= 45) & (rng3 >= 1.0) & ~exclude
    gxx, gyy = np.meshgrid(x0 + 0.5 + np.arange(W), y1 - 0.5 - np.arange(H))
    yy_ok = (gyy <= ys[1]) & (gyy >= ys[0])
    m &= yy_ok & (gxx <= foot.x.max() + 420)
    # keep the neighbourhood: from 15 m upslope of the foot eastwards
    pts = np.column_stack([gxx[m], gyy[m]]); d, _, _ = foot.at(pts)
    keep = np.zeros_like(m); keep[m] = d >= -15; m = keep
    sk = morphology.skeletonize(morphology.closing(m, morphology.disk(1)))
    lab = measure.label(sk, connectivity=2)
    walls = []
    for reg in measure.regionprops(lab):
        if reg.area < 4: continue
        rr, cc = reg.coords[:, 0], reg.coords[:, 1]
        X = x0 + 0.5 + cc; Y = y1 - 0.5 - rr
        # order the pixels along their principal axis and cut into ≤ 10 m pieces
        P = np.column_stack([X, Y]); mu = P.mean(0); u, s, vt = np.linalg.svd(P - mu, full_matrices=False)
        t = (P - mu) @ vt[0]; o = np.argsort(t); P = P[o]; t = t[o]
        h = float(rng3[rr, cc].max())
        for k in range(int(math.ceil((t[-1] - t[0] + 1e-6) / PIECE))):
            sel = (t >= t[0] + k * PIECE) & (t < t[0] + (k + 1) * PIECE + 1e-9)
            if sel.sum() < 3: continue
            Q = P[sel]; mq = Q.mean(0); _, _, v2 = np.linalg.svd(Q - mq, full_matrices=False)
            th = bearing(v2[0][0], v2[0][1])
            walls.append({"x": float(mq[0]), "y": float(mq[1]), "th": th, "len": float(sel.sum()), "h": round(h, 2), "unit": int(reg.label),
                          "line": [[round(float(Q[0][0]), 2), round(float(Q[0][1]), 2)], [round(float(Q[-1][0]), 2), round(float(Q[-1][1]), 2)]]})
    return walls


def analyse(sim=False, foot_def="consensus", aux=True):
    """One run of the whole test. The main run (consensus foot, affine registration) also writes the auxiliary
    files; the sensitivity runs (each single foot definition, the similarity registration) only return results."""
    class A_: pass
    args = A_(); args.sim = sim; args.foot = foot_def; args.out = "align.json" if aux else None
    F = json.load(open("foot.json"))
    if args.foot != "consensus":
        for r in F["profiles"]:
            v = r[args.foot] if not (isinstance(r[args.foot], float) and math.isnan(r[args.foot])) else r["foot"]
            r["foot_x"] = r["fx"] + v * r["nx"]; r["foot_y"] = r["y"] + v * r["ny"]
    foot = Foot(F)
    st = json.load(open("study.json")); poly = Polygon(st["poly"][0])
    par = json.load(open("parcels.json"))
    if args.sim:
        for p in par["parcels"]: p["rings"] = p["rings_sim"]
    tz = np.load("terrain.npz"); z = tz["z"].astype(float); x0, y1, W, H = [float(v) for v in tz["frame"]]; W, H = int(W), int(H)
    frame = box(x0, y1 - H, x0 + W, y1)
    L = tiles_layers()
    ys = (foot.yy.min(), foot.yy.max())
    win = box(foot.x.min() - 60, ys[0], foot.x.max() + 420, ys[1])

    # town grid from GSI road edges far from the foot
    segs = []
    for c, l in L["road_edge"]:
        if c != 2201: continue
        for x, y, th, w, _ in pieces(l.intersection(box(x0, ys[0] - 300, x0 + W, ys[1] + 300)), 10):
            d, _, _ = foot.at([(x, y)])
            if d[0] > 100: segs.append((th, w))
    grid, gridR = axial_mean([s[0] for s in segs], [s[1] for s in segs], 90)

    # regional front: the massif's eastern edge over the whole frame (Theil–Sen line of x on y)
    lab, _ = ndi.label(tz["mountain"]); top = np.unravel_index(np.nanargmax(np.where(tz["mountain"], z, -np.inf)), z.shape)
    mass = lab == lab[top]
    rows = [(y1 - 0.5 - r, x0 + 0.5 + np.nonzero(mass[r])[0].max()) for r in range(0, H, 4) if mass[r].any()]
    from scipy.stats import theilslopes
    yy_, xx_ = np.array(rows).T; sl, ic, _, _ = theilslopes(xx_, yy_)
    regional = bearing(sl, 1.0)
    near_front, _ = axial_mean(foot.dir, np.ones_like(foot.dir), 180)

    feats = {}
    # channel and banks
    ch = LineString(st["ichida"]).intersection(win)
    feats["channel"] = [ch]
    banks = [l.intersection(win) for c, l in L["water_edge"] if c in (5201, 5203)]
    feats["banks"] = [b for b in banks if not b.is_empty]
    # legal water (cadastral 水 parcels): their outline edges stand for their course
    lw = [Polygon(p["rings"][0]) for p in par["parcels"] if p["kind"] == "water" and p["rings"]]
    feats["legal_water"] = [LineString(q.exterior.coords) for q in lw]
    # back boundaries
    feats["backs"], feats["fronts"] = back_edges(par["parcels"], foot)
    # temple and shrine property
    priv = [(p, Polygon(p["rings"][0])) for p in par["parcels"] if p["kind"] == "private" and p["rings"]]
    temple_parcels = {}
    feats["temple"] = []
    for name, (lo, la) in TEMPLES.items():
        q = Point(*LL2P.transform(lo, la))
        cand = [c for c in priv if c[1].contains(q)]
        if not cand: temple_parcels[name] = None; continue
        c = cand[0]
        # how firmly the point sits in it: distance to the parcel's edge, and to the nearest other numbered parcel
        edge = round(c[1].exterior.distance(q), 1)
        other = round(min(g.distance(q) for pp, g in priv if g is not c[1]), 1)
        rec = {"chiban": c[0]["chiban"], "area_m2": round(c[1].area), "edge_m": edge, "next_private_m": other}
        # a point inside the 1 ha school parcel, or too close to an edge to tell, identifies nothing: leave it out
        rec["used"] = not is_school(c[0]) and edge >= 2.0
        temple_parcels[name] = rec
        if rec["used"]: feats["temple"].append(LineString(c[1].exterior.coords))
    osm = json.load(open("osm.json"))["elements"]
    for e in osm:
        if e["type"] == "way" and e["id"] in SHRINE_WAYS:
            feats["temple"].append(LineString([LL2P.transform(p["lon"], p["lat"]) for p in e["geometry"]]))
    # lanes
    feats["lanes"] = []
    for e in osm:
        t = e.get("tags", {})
        if e["type"] == "way" and e.get("geometry") and t.get("highway") in LANE_KINDS:
            g = LineString([LL2P.transform(p["lon"], p["lat"]) for p in e["geometry"]]).intersection(win)
            if not g.is_empty: feats["lanes"].append(g)
    # retaining walls from the DEM
    from PIL import Image, ImageDraw
    def mask(polys, buf):
        im = Image.new("1", (W, H), 0); dr = ImageDraw.Draw(im)
        for g in polys:
            g = g.buffer(buf)
            for p in getattr(g, "geoms", [g]):
                if p.geom_type == "Polygon" and len(p.exterior.coords) > 2:
                    dr.polygon([(x - x0 - 0.5, y1 - y - 0.5) for x, y in p.exterior.coords], fill=1)
        return np.asarray(im, dtype=bool)
    excl = mask([b for b in L["bld"] if b.intersects(win)], 1.5) | mask([Polygon(r[0]) for r in st["water_area"]], 2.0)
    walls = dem_walls(z, x0, y1, W, H, excl, foot, ys)
    # buildings: long axis of the minimum rotated rectangle, one piece per building
    brows = []
    for b in L["bld"]:
        if not b.intersects(win): continue
        for p in getattr(b, "geoms", [b]):
            if p.area < 15: continue
            r = np.asarray(p.minimum_rotated_rectangle.exterior.coords)
            e1, e2 = r[1] - r[0], r[2] - r[1]
            e = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2
            m = p.centroid; brows.append((m.x, m.y, bearing(e[0], e[1]), p.area, len(brows)))

    res = {"grid_deg": round(grid, 1), "grid_R": round(gridR, 2), "regional_front_deg": round(regional, 1),
           "near_front_deg": round(near_front, 1), "classes": {}}
    for name in ("channel", "banks", "legal_water", "backs", "fronts", "temple", "lanes"):
        rows = [p for u, g in enumerate(feats[name]) for p in pieces(g, unit=u)]
        res["classes"][name] = {"pieces": len(rows), "length_m": round(sum(r[3] for r in rows)),
                                "bands": [b for b in (classify(rows, foot, grid, bd) for bd in BANDS) if b]}
    wrows = [(w["x"], w["y"], w["th"], w["len"], w["unit"]) for w in walls]
    res["classes"]["walls"] = {"pieces": len(wrows), "length_m": round(sum(r[3] for r in wrows)),
                               "bands": [b for b in (classify(wrows, foot, grid, bd) for bd in WALL_BANDS) if b]}
    res["classes"]["buildings"] = {"pieces": len(brows), "bands": [b for b in (classify(brows, foot, grid, bd) for bd in BANDS) if b]}
    # wiggle tests for the long lines
    res["wiggle"] = {"channel": wiggle(ch, foot)}
    lwu = unary_union([LineString(q.exterior.coords) for q in lw])
    # the legal waterway's western (foot-side) edge: the westernmost crossing on each row
    res["wiggle"]["legal_water"] = wiggle(lwu, foot)
    res["wiggle"]["lanes_nearest"] = wiggle(unary_union(feats["lanes"]), foot)
    res["temple_parcels"] = temple_parcels
    # offsets from the foot, row by row
    lw_near = unary_union([q for q in lw if q.distance(foot.line) < 60])
    wa = unary_union([Polygon(r[0]) for r in st["water_area"]])
    privu = unary_union([Polygon(p["rings"][0]).buffer(0.2) for p in par["parcels"] if p["kind"] == "private" and p["rings"]])
    offs = {"legal_water": row_offsets(lw_near, foot, "area"), "channel": row_offsets(wa, foot, "area"),
            "lane": row_offsets(unary_union(feats["lanes"]), foot, "line"), "cadastre_west": row_offsets(privu, foot, "west")}
    res["offsets"] = {k: summarise_offsets(v) for k, v in offs.items()}
    # where the legal waterway and today's channel run together (≤ 5 m apart) and where they part
    lwd = dict(offs["legal_water"]); chd = dict(offs["channel"])
    both = sorted(set(lwd) & set(chd), reverse=True)
    res["legal_vs_channel"] = {"rows_both": len(both), "together_rows": int(sum(abs(lwd[y] - chd[y]) <= 5 for y in both)),
                               "apart_rows": int(sum(abs(lwd[y] - chd[y]) > 5 for y in both)),
                               "max_apart_m": round(max((abs(lwd[y] - chd[y]) for y in both), default=0), 1),
                               "together_y": [round(y, 1) for y in both if abs(lwd[y] - chd[y]) <= 5][:1] + [round(y, 1) for y in both if abs(lwd[y] - chd[y]) <= 5][-1:]}
    if args.out: json.dump(offs, open("offsets.json", "w"))
    res["courses"] = channel_courses(st, par["parcels"], "rings")
    res["walls"] = {"n": len(walls), "length_m": round(sum(w["len"] for w in walls)),
                    "h_median_m": round(float(np.median([w["h"] for w in walls])), 2) if walls else None}
    if args.out: json.dump(walls, open("walls.json", "w"))
    if args.out:
        json.dump({k: [list(map(list, g.coords)) if g.geom_type == "LineString" else [list(map(list, x.coords)) for x in g.geoms]
                       for g in v if not g.is_empty] for k, v in feats.items() if k in ("backs", "fronts")}, open("backs.json", "w"))
    return res


def main():
    res = analyse()
    variants = {"similarity registration": dict(sim=True), "foot A (mask edge)": dict(foot_def="A"), "foot B (plain + 1 m)": dict(foot_def="B"),
                "foot C (concavity)": dict(foot_def="C"), "foot D (hinge)": dict(foot_def="D")}
    rob, rob_band = {}, {}
    for name, kw in variants.items():
        r = analyse(aux=False, **kw)
        for cls, v in r["classes"].items():
            b = next((b for b in v["bands"] if b["from"] == (-15 if cls == "walls" else 0)), None)
            rob.setdefault(cls, []).append({"variant": name, **({k: b.get(k) for k in ("follow_foot_pct", "chance_pct", "p", "p_100", "n_disc", "n_units")} if b else {})})
            for bb in v["bands"]:
                rob_band.setdefault((cls, bb["from"]), []).append(bb)
        if kw.get("sim"): res["courses_sim"] = r["courses"]
        rob.setdefault("_offsets", []).append({"variant": name, "cadastre_west": r["offsets"]["cadastre_west"]["median_m"],
                                               "legal_water": r["offsets"]["legal_water"]["median_m"], "lane": r["offsets"]["lane"]["median_m"],
                                               "together_rows": r["legal_vs_channel"]["together_rows"], "wiggle_r": r["wiggle"]["channel"].get("wiggle_r")})
    # every band, not just the one next to the foot: in how many of the six runs does the excess hold?
    for cls, v in res["classes"].items():
        for bb in v["bands"]:
            if bb.get("p") is None: continue
            runs = [bb] + [x for x in rob_band.get((cls, bb["from"]), []) if x.get("p") is not None]
            bb["robust"] = {"runs": len(runs), "significant": sum(1 for x in runs if x["p"] < 0.05),
                            "significant_100": sum(1 for x in runs if x["p_100"] < 0.05),
                            "significant_both": sum(1 for x in runs if x["p"] < 0.05 and x["p_100"] < 0.05),
                            "above_chance": sum(1 for x in runs if x["follow_foot_pct"] > x["chance_pct"])}
    for cls, v in res["classes"].items():
        b = next((b for b in v["bands"] if b["from"] == (-15 if cls == "walls" else 0)), None)
        if not b or b.get("p") is None: continue
        runs = [b] + [x for x in rob.get(cls, []) if x.get("p") is not None]
        v["robust"] = {"runs": len(runs), "significant": sum(1 for x in runs if x["p"] < 0.05),
                       "significant_100": sum(1 for x in runs if x["p_100"] < 0.05),
                       "significant_both": sum(1 for x in runs if x["p"] < 0.05 and x["p_100"] < 0.05),
                       "above_chance": sum(1 for x in runs if x["follow_foot_pct"] > x["chance_pct"])}
    res["sensitivity"] = rob
    json.dump(res, open("align.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: (v.get("robust"), v["bands"][0] if v["bands"] else None) for k, v in res["classes"].items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
