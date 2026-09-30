#!/usr/bin/env python3
"""QA/QC gate for the Kansai page (kansai/index.html).

    python3 kansai/qa/run.py                  # full gate: render checks + data + claims + points + caveats
    python3 kansai/qa/run.py --write-caveats  # regenerate kansai/CAVEATS.md from the register, then check
    python3 kansai/qa/run.py --shots DIR      # also save a screenshot of every step

Exit status 0 = every check passed. Anything else blocks the deploy (see .github/workflows).

What it guarantees
  * every number a reader can see or hear (prose, charts, map labels, tooltips, legends, aria text)
    is registered in register.toml with a source and a status — an unregistered number fails;
  * every registered claim is still on the page (the register cannot drift from the text);
  * derived numbers are recomputed from the data embedded in the page (areas, shares, lengths,
    distances, arithmetic, model statistics) and must match what the text says;
  * every map point is within tolerance of an independently sourced coordinate (points.toml);
  * the rendered page has no JS errors, missing layers/views/legends, clipped or colliding labels,
    overflowing chart text, broken zoom, off-frame views, or sideways scrolling on phones;
  * kansai/CAVEATS.md is exactly what the register says it should be.
What it cannot do: judge whether a cited source is itself right. That is what the status field and
CAVEATS.md are for — anything not verified against a source is listed there.
"""
import argparse, json, math, re, shutil, subprocess, sys, tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    sys.exit("kansai/qa needs Python 3.11+ (tomllib)")

HERE = Path(__file__).resolve().parent
KANSAI = HERE.parent
sys.path.insert(0, str(HERE))
import tm  # noqa: E402

STATUSES = {"verified", "corrected", "derived", "method", "approximate", "author"}
NUM_RE = re.compile(r"\d(?:[\d,.]*\d)?")
WORD_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fifteen|twenty|"
                     r"thirty|forty|fifty|hundred|thousand|million|first|second|third|fourth|fifth|dozen|half)\b", re.I)


class Gate:
    def __init__(self):
        self.errors, self.warnings, self.passed = [], [], []

    def err(self, check, msg, where=""):
        self.errors.append((check, msg, where))

    def warn(self, check, msg, where=""):
        self.warnings.append((check, msg, where))

    def ok(self, check, msg):
        self.passed.append((check, msg))


# ------------------------------------------------------------------------------------------------ data
def load_page(path):
    html = path.read_text(encoding="utf-8")
    m = re.search(r"/\*GEO:BEGIN\*/(.*?)/\*GEO:END\*/", html, re.S)
    if not m:
        raise SystemExit(f"{path}: GEO block not found")
    return html, json.loads(m.group(1))


def stat(g, dotted):
    v = g["stats"]
    for k in dotted.split("."):
        v = v[k]
    return v


# ------------------------------------------------------------------------------------------------ geometry (SVG units, 1 unit = 100 m)
_TOK = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def rings(d):
    """Parse the build's path strings (M/L/H/V/Z, absolute or relative) into point lists."""
    out, cur, x, y, cmd, sx, sy = [], [], 0.0, 0.0, None, 0.0, 0.0
    toks = _TOK.findall(d)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                if cur:
                    out.append(cur); cur = []
                x, y = sx, sy
                continue
            continue
        if cmd in ("M", "m"):
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "m":
                nx += x; ny += y
            if cur:
                out.append(cur)
            cur = [(nx, ny)]; x, y, sx, sy = nx, ny, nx, ny
            cmd = "L" if cmd == "M" else "l"
        elif cmd in ("L", "l"):
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "l":
                nx += x; ny += y
            x, y = nx, ny; cur.append((x, y))
        elif cmd in ("H", "h"):
            v = float(toks[i]); i += 1
            x = v if cmd == "H" else x + v; cur.append((x, y))
        elif cmd in ("V", "v"):
            v = float(toks[i]); i += 1
            y = v if cmd == "V" else y + v; cur.append((x, y))
        else:
            raise ValueError(f"unsupported path command {cmd!r}")
    if cur:
        out.append(cur)
    return out


def _edges(rs):
    e = []
    for r in rs:
        for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
            if y1 != y2:
                e.append((min(y1, y2), max(y1, y2), x1, y1, x2, y2))
    e.sort()
    return e


def _rows(edge_lists, step):
    """Yield (y, [interval lists per polygon]) along horizontal scanlines (even-odd fill rule)."""
    ys = [e[0] for el in edge_lists for e in el] + [e[1] for el in edge_lists for e in el]
    if not ys:
        return
    y0, y1 = min(ys), max(ys)
    ptr = [0] * len(edge_lists); active = [[] for _ in edge_lists]
    y = y0 + step / 2
    while y < y1:
        ivs = []
        for k, el in enumerate(edge_lists):
            while ptr[k] < len(el) and el[ptr[k]][0] <= y:
                active[k].append(el[ptr[k]]); ptr[k] += 1
            active[k] = [e for e in active[k] if e[1] > y]
            xs = sorted(x1 + (y - yy1) * (x2 - x1) / (y2 - yy1) for (_, _, x1, yy1, x2, y2) in active[k]
                        if min(yy1, y2) <= y < max(yy1, y2))
            ivs.append(list(zip(xs[0::2], xs[1::2])))
        yield y, ivs
        y += step


def area_km2(d, step=0.1):
    tot = sum(sum(b - a for a, b in iv[0]) for _, iv in _rows([_edges(rings(d))], step))
    return tot * step * 0.01  # unit² → km²


def overlap_km2(d1, d2, step=0.1):
    tot = 0.0
    for _, (A, B) in _rows([_edges(rings(d1)), _edges(rings(d2))], step):
        for a0, a1 in A:
            for b0, b1 in B:
                tot += max(0.0, min(a1, b1) - max(a0, b0))
    return tot * step * 0.01


def length_km(d):
    return sum(math.dist(p, q) for r in rings(d) for p, q in zip(r, r[1:])) * 0.1


def inside(d, x, y):
    c = False
    for r in rings(d):
        for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
    return c


# ------------------------------------------------------------------------------------------------ checks
def check_derived(gate, g, claim):
    c = claim.get("check")
    if not c:
        return
    cid = claim["id"]
    L = g["layers"]
    try:
        if "stat" in c:
            v = stat(g, c["stat"]); shown = c.get("fmt", "{}").format(v)
            if not any(shown in m for m in claim.get("match", []) + claim.get("exact", [])):
                gate.err("derived", f"data says {c['stat']} = {v} → “{shown}”, but the text says {claim['match']}", cid)
            else:
                gate.ok("derived", f"{cid}: {c['stat']} = {v} ↔ “{shown}”")
            return
        if "area" in c:
            got = area_km2(L[c["area"]]); what = f"area of {c['area']}"
        elif "share" in c:
            a, b = c["share"]; got = 100 * area_km2(L[a]) / area_km2(L[b]); what = f"{a} as % of {b}"
        elif "overlap" in c:
            a, b = c["overlap"]; got = 100 * overlap_km2(L[a], L[b]) / area_km2(L[a]); what = f"% of {a} inside {b}"
        elif "length" in c:
            got = length_km(L[c["length"]]); what = f"length of {c['length']}"
        elif "dist" in c:
            a, b = (g["pts"][k] for k in c["dist"]); got = math.dist(a, b) * 0.1; what = f"distance {c['dist'][0]}–{c['dist'][1]} (km)"
        elif "calc" in c:
            if not re.fullmatch(r"[\d\s.+\-*/()]+", c["calc"]):
                raise ValueError("calc may only contain numbers and + - * / ( )")
            got = eval(c["calc"], {"__builtins__": {}}); what = c["calc"]
        elif "valley_ve" in c:
            pv = g["profile"]; B = pv["marks"]["hongu"][0]; KM = pv["river_km"]; ce = pv["coast"][-1][1]
            cpx = 880 / (B + 3 * (KM - B + ce)); ve = (250 / 1900) / (cpx / 1000)
            got = ve if c["valley_ve"] == "up" else ve / 3; what = f"vertical exaggeration ({c['valley_ve']}stream)"
        else:
            raise ValueError(f"unknown check {c}")
    except Exception as e:  # a broken check is itself a failure
        gate.err("derived", f"check could not run: {e}", cid); return
    exp, tol = c["expect"], c.get("tol", 0.01)
    bad = abs(got - exp) > (tol * abs(exp) if c.get("relative") else tol)
    if bad:
        gate.err("derived", f"{what} = {got:.4g}, the text relies on {exp} (± {tol}{' rel' if c.get('relative') else ''})", cid)
    else:
        gate.ok("derived", f"{cid}: {what} = {got:.4g} ≈ {exp}")


def check_register(gate, reg, inventory, g):
    texts = [it["text"] for it in inventory]
    ids = set()
    for c in reg.get("claim", []):
        cid = c.get("id", "?")
        if cid in ids:
            gate.err("register", "duplicate claim id", cid)
        ids.add(cid)
        if c.get("status") not in STATUSES:
            gate.err("register", f"status must be one of {sorted(STATUSES)}", cid)
        if c.get("status") in {"verified", "corrected", "approximate"} and not c.get("source"):
            gate.err("register", "verified/corrected claims need a source", cid)
        if c.get("status") in {"corrected", "approximate", "author"} and not c.get("note"):
            gate.err("register", "corrected/approximate/author claims need a note for CAVEATS.md", cid)
        if not c.get("match") and not c.get("exact"):
            gate.err("register", "claim has no match/exact text", cid)
        for m in c.get("match", []):
            if not any(m in t for t in texts):
                gate.err("stale-claim", f"“{m}” is no longer on the page — update or remove the claim", cid)
        for m in c.get("exact", []):
            if m not in texts:
                gate.err("stale-claim", f"“{m}” is no longer a text item on the page — update or remove the claim", cid)
        check_derived(gate, g, c)
    # coverage: every number on the page must sit inside a registered claim or a declared identifier
    idents = [(re.compile(i["pattern"]), i["why"]) for i in reg.get("identifier", [])]
    seen_uncovered = set()
    for it in inventory:
        t = it["text"]; cov = []
        for c in reg.get("claim", []):
            for m in c.get("match", []):
                for mm in re.finditer(re.escape(m), t):
                    cov.append(mm.span())
            if t in c.get("exact", []):   # short labels (“86%”, “2025”) only count when they are the whole item
                cov.append((0, len(t)))
        for rx, _ in idents:
            for mm in rx.finditer(t):
                cov.append(mm.span())
        for rx in (NUM_RE, WORD_RE):
            for mm in rx.finditer(t):
                a, b = mm.span()
                if not any(s <= a and b <= e for s, e in cov):
                    key = (mm.group(0), t)
                    if key in seen_uncovered:
                        continue
                    seen_uncovered.add(key)
                    ctx = t[max(0, a - 50): b + 50]
                    gate.err("unsourced-number", f"“{mm.group(0)}” has no entry in register.toml: …{ctx}…", it["src"])
    if not any(e[0] == "unsourced-number" for e in gate.errors):
        gate.ok("coverage", f"every number in {len(inventory)} text items is registered")


def check_points(gate, pts_ref, g, used):
    P = pts_ref.get("points", {})
    for key in sorted(set(used)):
        if key.startswith("@"):
            lon, lat = map(float, key[1:].split(","))
            want = tm.to_svg(lon, lat, g["origin"]); got = g.get("at", {}).get(key)
            if not got or math.dist(want, got) * 100 > 1:
                gate.err("points", f"label anchor {key} is not where its coordinates say", key)
            continue
        if key not in P:
            gate.err("points", "map point has no sourced reference in points.toml", key); continue
    for key, p in P.items():
        if key not in g["pts"]:
            gate.err("points", "reference point missing from the page data", key); continue
        if key not in used:
            gate.warn("points", "reference point not used by the page (stale entry?)", key)
        if not p.get("source"):
            gate.err("points", "no source", key)
        if "inside" in p:
            if not inside(g["layers"][p["inside"]], *g["pts"][key]):
                gate.err("points", f"derived point is not inside layer {p['inside']}", key)
            continue
        want = tm.to_svg(p["lon"], p["lat"], g["origin"])
        off = math.dist(want, g["pts"][key]) * 100
        if off > p["tol_m"]:
            gate.err("points", f"{off:.0f} m from its reference ({p['source']}); tolerance {p['tol_m']} m", key)
    if not any(e[0] == "points" for e in gate.errors):
        gate.ok("points", f"{len(P)} map points within tolerance of sourced coordinates")


def check_geo(gate, g):
    for k in ("frame", "views", "layers", "pts", "stats", "origin", "crs"):
        if k not in g:
            gate.err("geo", f"GEO.{k} missing")
    if g.get("crs") != "EPSG:6674":
        gate.err("geo", f"unexpected CRS {g.get('crs')}")
    F = g["frame"]
    for k, v in g.get("views", {}).items():
        if not (F[0] - 1 <= v[0] < v[2] <= F[2] + 1 and F[1] - 1 <= v[1] < v[3] <= F[3] + 1):
            gate.err("geo", f"view {k} {v} is not inside the frame", k)
    for k, (x, y) in g.get("pts", {}).items():
        if not (F[0] <= x <= F[2] and F[1] <= y <= F[3]):
            gate.err("geo", f"point {k} lies outside the frame", k)
    for k, d in g.get("layers", {}).items():
        try:
            rings(d)
        except Exception as e:
            gate.err("geo", f"layer {k} does not parse: {e}", k)
    # the projection the page was built with must be the one the QA uses
    sh = g["pts"].get("shingu")
    if sh and math.dist(tm.to_svg(135.9925, 33.7241, g["origin"]), sh) * 100 > 1:
        gate.err("geo", "GEO.origin does not reproduce the city-hall point; projection mismatch")
    gate.ok("geo", f"{len(g['layers'])} layers, {len(g['views'])} views, {len(g['pts'])} points parse and sit in the frame")


# ------------------------------------------------------------------------------------------------ CAVEATS.md
def caveats_md(reg, pts_ref):
    C = reg.get("claim", [])
    def block(status):
        rows = [c for c in C if c["status"] == status]
        return "\n".join(f"- **{c.get('title') or (c.get('match') or c.get('exact'))[0]}** — {c['note']}"
                         + (f" Source: {c['source']}" if c.get("source") else "")
                         + (f" <{c['url']}>" if c.get("url") else "") for c in rows) or "- none"
    low = [(k, p) for k, p in pts_ref.get("points", {}).items() if p.get("confidence", "high") in ("low", "low–medium", "medium–low")]
    lims = reg.get("limitation", [])
    by_topic = {}
    for l in lims:
        by_topic.setdefault(l["topic"], []).append(l)
    out = ["# Kansai page — caveats and imperfections", "",
           "Generated from `kansai/qa/register.toml` and `kansai/qa/points.toml` by `python3 kansai/qa/run.py --write-caveats`.",
           "Do not edit by hand: the QA gate fails if this file and the register disagree.", "",
           "## Corrections made to the draft text", "The page follows the source, not the draft, in these places.", "", block("corrected"), "",
           "## Not independently verified", "These come from the author's text. No source was found or checked for them yet.", "", block("author"), "",
           "## Verified, but rounded or simplified on the page", "", block("approximate"), "",
           "## Map positions with low confidence", ""]
    out += [f"- **{k}** ({p.get('name', '')}) — {p.get('note', p['source'])}; drawn within {p['tol_m']} m." for k, p in low] or ["- none"]
    out += ["", "## Errors the QA gate caught and fixed", ""]
    out += [f"- **{f['what']}** — {f['how']}." for f in reg.get("fix", [])] or ["- none"]
    out += ["", "## Data and method limitations", ""]
    for topic, items in by_topic.items():
        out.append(f"### {topic}")
        out += [f"- **{l['title']}** — {l['text']}" for l in items]
        out.append("")
    n = {s: sum(1 for c in C if c["status"] == s) for s in sorted(STATUSES)}
    out += ["## Register totals", "", " · ".join(f"{k}: {v}" for k, v in n.items()) + f" · map points: {len(pts_ref.get('points', {}))}", ""]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page", default=str(KANSAI / "index.html"))
    ap.add_argument("--write-caveats", action="store_true")
    ap.add_argument("--shots")
    ap.add_argument("--report", help="reuse an existing render report instead of launching the browser")
    ap.add_argument("--json", help="write the full result as JSON")
    ap.add_argument("--caveats", default=str(KANSAI / "CAVEATS.md"), help="path of the generated caveats file")
    a = ap.parse_args()
    gate = Gate()
    page = Path(a.page)
    html, g = load_page(page)
    reg = tomllib.loads((HERE / "register.toml").read_text(encoding="utf-8"))
    pts_ref = tomllib.loads((HERE / "points.toml").read_text(encoding="utf-8"))

    check_geo(gate, g)

    # render pass (browser)
    if a.report:
        rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    else:
        node = shutil.which("node")
        if not node:
            raise SystemExit("node is required for the render checks (npm i playwright)")
        tmp = Path(tempfile.mkdtemp()) / "render.json"
        cmd = [node, str(HERE / "check_render.mjs"), str(page), str(tmp)] + (["--shots", a.shots] if a.shots else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode or not tmp.exists():
            raise SystemExit(f"render checks failed to run:\n{r.stdout}\n{r.stderr}")
        rep = json.loads(tmp.read_text(encoding="utf-8"))
    for e in rep["errors"]:
        gate.err("render/" + e["check"], e["msg"], e.get("where", ""))
    for w in rep["warnings"]:
        gate.warn("render/" + w["check"], w["msg"], w.get("where", ""))
    if not rep["errors"]:
        gate.ok("render", "no JS errors; refs, land fill, cameras, labels, charts, zoom, mini-maps and mobile layout pass")

    check_register(gate, reg, rep["inventory"], g)
    check_points(gate, pts_ref, g, rep["usedPoints"])

    md = caveats_md(reg, pts_ref)
    cav = Path(a.caveats)
    if a.write_caveats:
        cav.write_text(md, encoding="utf-8")
    if not cav.exists() or cav.read_text(encoding="utf-8") != md:
        gate.err("caveats", "kansai/CAVEATS.md is out of date — run: python3 kansai/qa/run.py --write-caveats")
    else:
        gate.ok("caveats", "CAVEATS.md matches the register")

    # report
    print(f"\nKansai QA/QC — {page}")
    for c, m in gate.passed:
        print(f"  ✓ {c:12s} {m}")
    for c, m, w in gate.warnings:
        print(f"  ! {c:12s} {m}" + (f"  [{w}]" if w else ""))
    for c, m, w in gate.errors:
        print(f"  ✗ {c:12s} {m}" + (f"  [{w}]" if w else ""))
    print(f"\n{len(gate.errors)} error(s), {len(gate.warnings)} warning(s)")
    if a.json:
        Path(a.json).write_text(json.dumps({"errors": gate.errors, "warnings": gate.warnings, "passed": gate.passed}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if gate.errors else 0)


if __name__ == "__main__":
    main()
