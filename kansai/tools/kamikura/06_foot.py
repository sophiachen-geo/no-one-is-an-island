"""Kamikura micro-study, step 6: where, geometrically, does Kamikura-yama stop and the lowland begin?

Reads terrain.npz / terrain.json (02), terrain_plus.npz (05), study.json (03). Writes foot.json.

The foot is located independently four ways on cross-profiles every 2 m along the mountain front, each profile
perpendicular to the front (smoothed over 41 m) and sampled every 0.5 m from 40 m upslope to 60 m downslope:
  A  mask       edge of the mountain mask of step 2 (≥ 1 m above the plain and steeper than 12° or > 3 m above it)
  B  plain + 1  where the ground first stands 1 m above this profile's own plain (median of 20–60 m downslope)
  C  concavity  the most concave point (profile curvature, σ 2.5 m) between the plain and 10 m above it
  D  hinge      the knee of a continuous two-segment straight-line fit to the profile (least squares, 0.5 m steps)
Channel cells (GSI water area + 1.5 m) are left out of B–D. The consensus foot is the per-profile median of the
four; the band is their range. Positions are signed metres along the profile: negative = upslope (west).
"""
import json, math
import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely import contains_xy

STEP, HALF_UP, HALF_DN, DS = 2.0, 40.0, 60.0, 0.5
Y_RANGE = (-252660.0, -252040.0)          # northings covered: the study area ± ~180 m along the front


def front_reference(mountain, x0, y1, ys):
    """x of the mountain's eastern edge on each row (easternmost mountain cell connected to the slope), smoothed."""
    xs = []
    for y in ys:
        r = int(round(y1 - 0.5 - y)); row = mountain[r]
        cols = np.nonzero(row)[0]
        xs.append(x0 + 0.5 + cols.max() if len(cols) else np.nan)
    xs = np.array(xs)
    ok = ~np.isnan(xs)
    xs = np.interp(np.arange(len(xs)), np.nonzero(ok)[0], xs[ok])
    return xs


def smooth(a, n):
    k = np.ones(n) / n; pad = n // 2
    return np.convolve(np.pad(a, pad, mode="edge"), k, mode="valid")


def hinge(s, z):
    """Continuous two-segment least-squares fit; returns the knee position and the RMS residual."""
    best = (None, np.inf)
    for k in np.arange(s.min() + 6, s.max() - 6, 0.5):
        X = np.column_stack([np.ones_like(s), np.minimum(s - k, 0), np.maximum(s - k, 0)])
        coef, res, *_ = np.linalg.lstsq(X, z, rcond=None)
        rss = float(np.sum((X @ coef - z) ** 2))
        if rss < best[1]: best = (float(k), rss, coef)
    return best[0], math.sqrt(best[1] / len(s)), best[2]


def main():
    tz = np.load("terrain.npz"); tp = np.load("terrain_plus.npz"); st = json.load(open("study.json"))
    z = tz["z"].astype(np.float64); prof = tp["prof"].astype(np.float64)
    # only the massif of Kamikura-yama / 千穂ヶ峰 (the mask component holding the frame's highest ground); the
    # mask also holds smaller hills to the east, which are not this front
    lab, _ = ndi.label(tz["mountain"])
    top = np.unravel_index(np.nanargmax(np.where(tz["mountain"], z, -np.inf)), z.shape)
    mountain = lab == lab[top]
    x0, y1, W, H = [float(v) for v in tz["frame"]]
    zf = np.where(np.isnan(z), np.nanmedian(z), z)
    chan = unary_union([Polygon(r[0]) for r in st["water_area"]]).buffer(1.5)

    ys = np.arange(Y_RANGE[1], Y_RANGE[0], -STEP)               # north → south
    fx = smooth(front_reference(mountain, x0, y1, ys), 21)      # 21 rows × 2 m ≈ 41 m
    # profile direction: perpendicular to the smoothed front, pointing east (downslope)
    dx = np.gradient(fx); dy = np.full_like(fx, -STEP)
    tx, ty = dx / np.hypot(dx, dy), dy / np.hypot(dx, dy)
    nx, ny = -ty, tx                                            # rotate tangent (pointing south) by +90° → east
    flip = nx < 0; nx[flip] *= -1; ny[flip] *= -1
    s = np.arange(-HALF_UP, HALF_DN + DS / 2, DS)

    def at(arr, px, py, order=1):
        c = px - x0 - 0.5; r = y1 - 0.5 - py
        return ndi.map_coordinates(arr, [r, c], order=order, mode="nearest")

    rows = []
    for i, (cx, cy) in enumerate(zip(fx, ys)):
        px, py = cx + s * nx[i], cy + s * ny[i]
        zp = at(zf, px, py); kp = at(prof, px, py); mp = at(mountain.astype(float), px, py, 0) > 0.5
        wet = contains_xy(chan, px, py)
        dry = ~wet
        # A: last mountain sample before the first long run of lowland (walking downslope)
        inside = np.nonzero(mp)[0]
        A = float(s[inside.max()]) + DS / 2 if len(inside) else np.nan
        # B: own plain = median of dry ground 20–60 m downslope; foot = last sample ≥ plain + 1 m walking downslope
        sel = (s >= 20) & dry
        plain = float(np.median(zp[sel])) if sel.sum() > 10 else np.nan
        above = np.nonzero((zp >= plain + 1.0) & dry)[0]
        # the first run of ≥ plain+1 that is connected to the upslope end
        B = np.nan
        if len(above) and above[0] == 0:
            run_end = above[0]
            for j in above[1:]:
                if j == run_end + 1: run_end = j
                else: break
            B = float(s[run_end]) + DS / 2
        # C: most concave point among dry samples between the plain and 10 m above it
        band = dry & (zp >= plain - 0.5) & (zp <= plain + 10.0)
        C = float(s[band][np.argmin(kp[band])]) if band.sum() > 5 else np.nan
        # D: two-segment hinge on dry samples
        D, rms, coef = hinge(s[dry], zp[dry]) if dry.sum() > 40 else (np.nan, np.nan, None)
        # steepest 1 m step within ±6 m of the consensus (a wall or a cut face reads as > 45°)
        rows.append({"y": float(cy), "fx": float(cx), "nx": float(nx[i]), "ny": float(ny[i]), "plain": plain,
                     "A": A, "B": B, "C": C, "D": D, "D_rms": rms,
                     "D_up_deg": math.degrees(math.atan(abs(coef[1]))) if coef is not None else None,
                     "D_dn_deg": math.degrees(math.atan(abs(coef[2]))) if coef is not None else None})

    defs = ["A", "B", "C", "D"]
    M = np.array([[r[d] for d in defs] for r in rows], dtype=float)
    ok = ~np.isnan(M).any(axis=1)
    med = np.nanmedian(M, axis=1); rng = np.nanmax(M, axis=1) - np.nanmin(M, axis=1)
    for r, m, g in zip(rows, med, rng):
        r["foot"] = float(m); r["range"] = float(g)
        r["foot_x"] = r["fx"] + m * r["nx"]; r["foot_y"] = r["y"] + m * r["ny"]
    # steepness at the foot: the steepest 1 m-step (between samples 1 m apart) within 6 m upslope of the foot
    for r in rows:
        sp = np.arange(r["foot"] - 6, r["foot"] + 1.01, 0.5)
        px, py = r["fx"] + sp * r["nx"], r["y"] + sp * r["ny"]
        zz = at(zf, px, py)
        r["step_deg"] = float(np.degrees(np.arctan(np.max(np.abs(zz[2:] - zz[:-2]))))) if len(zz) > 2 else None
        r["rise_6m"] = float(zz[0] - zz[-1])
    pair = {}
    for a in range(4):
        for b in range(a + 1, 4):
            d = np.abs(M[ok, a] - M[ok, b]); pair[defs[a] + defs[b]] = round(float(np.median(d)), 2)
    dev = np.abs(M[ok] - med[ok, None])
    summ = {"profiles": len(rows), "complete": int(ok.sum()), "pair_median_abs_m": pair,
            "range_median_m": round(float(np.median(rng[ok])), 2), "range_p90_m": round(float(np.percentile(rng[ok], 90)), 2),
            "within5_pct": round(100 * float((rng[ok] <= 5).mean()), 1),
            "dev_from_consensus_median_m": {d: round(float(np.median(dev[:, k])), 2) for k, d in enumerate(defs)},
            "D_up_deg_median": round(float(np.nanmedian([r["D_up_deg"] for r in rows])), 1),
            "D_dn_deg_median": round(float(np.nanmedian([r["D_dn_deg"] for r in rows])), 1),
            "step_deg_median": round(float(np.nanmedian([r["step_deg"] for r in rows])), 1),
            "step_over45_pct": round(100 * float(np.mean([r["step_deg"] > 45 for r in rows])), 1)}
    # the consensus line and its direction (axial, N-based, clockwise)
    line = LineString([(r["foot_x"], r["foot_y"]) for r in rows])
    dxs = rows[-1]["foot_x"] - rows[0]["foot_x"]; dys = rows[-1]["foot_y"] - rows[0]["foot_y"]
    summ["chord_bearing"] = round(math.degrees(math.atan2(dxs, dys)) % 180, 1)
    summ["length_m"] = round(line.length, 1)
    poly = Polygon(st["poly"][0])
    inside = [r for r in rows if poly.buffer(30).contains(Point(r["foot_x"], r["foot_y"]))]
    summ["study_profiles"] = len(inside)
    Mi = np.array([[r[d] for d in defs] for r in inside], dtype=float)
    oi = ~np.isnan(Mi).any(axis=1)
    summ["study_range_median_m"] = round(float(np.median((np.nanmax(Mi, 1) - np.nanmin(Mi, 1))[oi])), 2)
    summ["study_within5_pct"] = round(100 * float(((np.nanmax(Mi, 1) - np.nanmin(Mi, 1))[oi] <= 5).mean()), 1)
    json.dump({"summary": summ, "profiles": rows, "s": [float(-HALF_UP), float(HALF_DN), DS]}, open("foot.json", "w"))
    print(json.dumps(summ, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
