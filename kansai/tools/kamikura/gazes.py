"""Kamikura micro-study: comparing gazes (まなざし). Summarises kansai/field/gazes.csv for the page.

The table codes every image of Kamikura that six publishers put on their pages (the promotional gaze), the two in
Shingū's 2013 master plan (municipal), the Kubo studio's 1913 album (historical) and our own photographs at the foot
(researcher) by the frame of Gou & Shibata (2017): where the camera stands, whether the town is in the frame as a view, the
breadth of view, and up to two of their landscape categories (one added: Channel). See kansai/field/README.md.

    python3 gazes.py <kansai folder>     # rewrite only the "gaze" key of data/kamikura.js
09_export.py calls summary() when it writes the whole file.
"""
import csv, json, math, re, sys
from collections import Counter

POSITIONS = ["mountain", "threshold", "foot", "town"]       # where the camera stands, from the summit down to the town
ROWS = ["promotional", "municipal", "historical", "researcher"]


def _foot_line(kmk):
    """The foot as a polyline in page units (the M/l path of layers.foot)."""
    pts, x, y = [], 0.0, 0.0
    for cmd, args in re.findall(r"([MmLl])([^MmLl]*)", kmk["layers"]["foot"]):
        nums = [float(v) for v in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", args)]
        for a, b in zip(nums[0::2], nums[1::2]):
            if cmd in "ML": x, y = a, b
            else: x, y = x + a, y + b
            pts.append((x, y))
    return pts


def _dist_m(p, line):
    best = 1e18
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(ax + t * dx - p[0], ay + t * dy - p[1]))
    return best * 100                                        # 1 page unit = 100 m


def summary(kansai, kmk=None):
    rows = list(csv.DictReader(open(f"{kansai}/field/gazes.csv", encoding="utf-8")))
    if kmk is None:
        s = open(f"{kansai}/data/kamikura.js", encoding="utf-8").read(); kmk = json.loads(s[s.index("{"):s.rindex("}") + 1])
    out = {"positions": POSITIONS, "rows": []}
    for g in ROWS:
        R = [r for r in rows if r["gaze"] == g]
        photos = [r for r in R if r["position"] in POSITIONS]
        cats = Counter(c for r in photos for c in (r["category_1"], r["category_2"]) if c)
        out["rows"].append({
            "key": g, "n": len(photos), "maps": len(R) - len(photos),
            "publishers": len({r["publisher"] for r in R}),
            "pos": [sum(r["position"] == p for r in photos) for p in POSITIONS],
            "town": sum(r["town"] == "yes" for r in photos),
            "festival": sum(r["festival"] == "yes" for r in photos),
            "breadth": {b: sum(r["breadth"] == b for r in photos) for b in ("intraocular", "ocular", "extraocular")},
            "cats": dict(cats.most_common()),
        })
    # our photographs: distance from the measured foot (fieldnotes.js holds their EXIF positions in page units)
    fs = open(f"{kansai}/data/fieldnotes.js", encoding="utf-8").read()
    ph = {p["src"].rsplit("/", 1)[-1]: p for p in json.loads(fs[fs.index("{"):fs.rindex("}") + 1])["town"]["photos"]}
    foot = _foot_line(kmk)
    ours = []
    for r in rows:
        if r["gaze"] != "researcher": continue
        p = ph[r["image"]]
        ours.append({"id": r["id"], "file": r["image"], "pos": r["position"], "dist_m": round(_dist_m((p["x"], p["y"]), foot)),
                     "cat": r["category_1"]})
    out["ours"] = ours
    d = [o["dist_m"] for o in ours]
    out["ours_dist_m"] = [min(d), max(d)] if d else None
    return out


if __name__ == "__main__":
    K = sys.argv[1] if len(sys.argv) > 1 else "."
    P = f"{K}/data/kamikura.js"
    s = open(P, encoding="utf-8").read(); data = json.loads(s[s.index("{"):s.rindex("}") + 1])
    data["gaze"] = summary(K, data)
    open(P, "w", encoding="utf-8").write("window.__KMK=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(json.dumps(data["gaze"]["rows"], ensure_ascii=False)[:1500]); print(data["gaze"]["ours_dist_m"])
