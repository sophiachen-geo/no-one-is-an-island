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


_BLD = {}
_KMK = {}


def kmk_data():
    """The Kamikura micro-study (kansai/data/kamikura.js, built by kansai/tools/kamikura)."""
    if not _KMK:
        import os
        raw = (Path(os.environ.get("KANSAI_DATA", KANSAI / "data")) / "kamikura.js").read_text(encoding="utf-8").strip()
        _KMK.update(json.loads(raw[raw.index("=") + 1:].rstrip(";")))
    return _KMK


_FN = {}


def fn_data():
    """The field notes (kansai/data/fieldnotes.js, built by kansai/tools/bike)."""
    if not _FN:
        import os
        raw = (Path(os.environ.get("KANSAI_DATA", KANSAI / "data")) / "fieldnotes.js").read_text(encoding="utf-8").strip()
        _FN.update(json.loads(raw[raw.index("=") + 1:].rstrip(";")))
    return _FN


def fn_value(dotted):
    v = fn_data()
    for k in dotted.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def kmk_value(dotted):
    v = kmk_data()
    for k in dotted.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def shoelace_m2(d):
    """Area of an SVG path (page units, even–odd rings) in square metres."""
    tot = 0.0
    for r in rings(d):
        tot += sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1])) / 2
    return abs(tot) * 1e4


def bld_counts(g):
    """Re-count the building footprints (one point inside each) against the page's own hazard layers."""
    if _BLD:
        return _BLD
    from geomfast import Region
    import os
    raw = (Path(os.environ.get("KANSAI_DATA", KANSAI / "data")) / "buildings.js").read_text(encoding="utf-8").strip()
    B = json.loads(raw[raw.index("=") + 1:].rstrip(";"))
    L = g["layers"]
    TS, FK, FI, CT = Region(L["tsunami"]), Region(L["flood"]), Region(L["flood_ichida"]), Region(L["shingu"])
    c = B["cent"]; n = ts = fl = ei = 0
    for i in range(0, len(c), 2):
        x, y = c[i], c[i + 1]
        if not CT.contains(x, y):
            continue
        n += 1; t = TS.contains(x, y); f = FK.contains(x, y) or FI.contains(x, y)
        ts += t; fl += f; ei += (t or f)
    _BLD.update(total=n, tsunami=ts, flood=fl, either=ei, either_pct=100 * ei / n)
    if B.get("counts", {}).get("total") != n:
        raise ValueError("buildings.js counts differ from a re-count — rebuild with tools/17_round3.py")
    return _BLD


# ------------------------------------------------------------------------------------------------ checks
def check_derived(gate, g, claim):
    c = claim.get("check")
    if not c:
        return
    cid = claim["id"]
    L = g["layers"]
    try:
        if "stat" in c or ("kmk" in c and "fmt" in c) or ("fn" in c and "fmt" in c):
            v = stat(g, c["stat"]) if "stat" in c else kmk_value(c["kmk"]) if "kmk" in c else fn_value(c["fn"]); shown = c.get("fmt", "{}").format(v)
            src = c["stat"] if "stat" in c else ("kamikura." + c["kmk"]) if "kmk" in c else ("fieldnotes." + c["fn"])
            if not any(shown in m for m in claim.get("match", []) + claim.get("exact", [])):
                gate.err("derived", f"data says {src} = {v} → “{shown}”, but the text says {claim.get('match') or claim.get('exact')}", cid)
            else:
                gate.ok("derived", f"{cid}: {src} = {v} ↔ “{shown}”")
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
        elif "kmk" in c:
            got = float(kmk_value(c["kmk"])); what = f"kamikura.{c['kmk']}"
        elif "fn" in c:
            got = float(fn_value(c["fn"])); what = f"fieldnotes.{c['fn']}"
        elif "bld" in c:
            got = bld_counts(g)[c["bld"]]; what = f"buildings: {c['bld']} (re-counted from kansai/data/buildings.js)"
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


def literal_spans(m, t):
    """Every occurrence of the literal text m in t. A plain search: with several hundred match strings, compiling
    each as a regex on every text item outran re's pattern cache and made the gate minutes slower."""
    i = t.find(m)
    while i >= 0:
        yield i, i + len(m)
        i = t.find(m, i + 1)


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
        if it["src"] in FN_VERIFIED:      # every cell recomputed from kansai/data/fieldnotes.js by check_fn
            continue
        t = it["text"]; cov = []
        for c in reg.get("claim", []):
            for m in c.get("match", []):
                cov.extend(literal_spans(m, t))
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


FN_VERIFIED = {"td#fnopts", "text#fnprof"}


def fn_table_rows(pair):
    """The route table as the page must show it, recomputed here from the data (same rounding as the page)."""
    D = fn_data(); R = D["region"]; C = {c["id"]: c for c in R["chains"]}
    rows = []
    for i, O in enumerate(R["options"][pair]["list"]):
        labs = []
        for cid, o in O["seq"]:
            c = C[cid]
            if c["len"] < 2000:
                continue
            r = c["refs"][0].split(";")[0] if c["refs"] else None
            top = c["gsi"][0][0] if c["gsi"] else ""
            lab = ("R" + r) if r and top == "国道" else ("県道" + r) if r and top == "都道府県道" else "municipal road" if top == "市区町村道等" else "national road" if top == "国道" else "road"
            if c["unp"] > 0.25 * c["len"]:
                lab += " (partly unpaved)"
            if not labs or labs[-1] != lab:
                labs.append(lab)
        on = {cid for cid, o in O["seq"]}
        mm = hr = None
        for cl in R["closures"]:
            if any(int(k) in on and v >= 200 for k, v in cl["chains"].items()):
                mm = cl["mm"] if mm is None else min(mm, cl["mm"])
                if cl.get("hr"):
                    hr = cl["hr"] if hr is None else min(hr, cl["hr"])
        hz = O["haz"]; ls = hz.get("ls_yellow", 0) + hz.get("ls_red", 0)
        g = "unreliable*" if O["gmax"] > 25 else f"{O['gmax']:.1f} %"
        rows.append([f"{chr(65 + i)} · " + " → ".join(labs), f"{O['len'] / 1000:.1f}", str(O["up"]), str(O["down"]), g,
                     f"{O['tun'][0]} · {O['tun'][1] / 1000:.1f} km", (f"{mm} mm" + (f" or {hr} mm/h" if hr else "")) if mm else "—", f"{hz.get('tsunami_l2_2016', 0) / 1000:.1f} km", f"{ls / 1000:.1f} km"])
    return rows


def check_fn(gate, rep, pts_ref, mreg):
    """Field notes: the route table and profile follow the data; the photographs are ours, registered, stripped of
    location metadata and placed in the town; the town labels sit on their independent references."""
    try:
        D = fn_data()
    except Exception as e:
        gate.err("fieldnotes", f"kansai/data/fieldnotes.js could not be read: {e}"); return
    F = rep.get("fn") or {}
    n_bad = 0
    for pair in D["region"]["options"]:
        want, got = fn_table_rows(pair), (F.get("tables") or {}).get(pair)
        if got is None:
            gate.err("fieldnotes", f"the render pass did not report the table for {pair}"); n_bad += 1; continue
        for i, (w, g) in enumerate(zip(want, got)):
            if w != g:
                gate.err("fieldnotes", f"{pair} row {chr(65 + i)}: page shows {g}, the data gives {w}"); n_bad += 1
        if len(want) != len(got):
            gate.err("fieldnotes", f"{pair}: {len(got)} rows on the page, {len(want)} in the data"); n_bad += 1
        pv = (F.get("prof") or {}).get(pair) or {}
        O = D["region"]["options"][pair]["list"][0]
        name = {"hongu-hayatama": "Hongū → Hayatama", "hayatama-nachi": "Hayatama → Nachi", "nachi-hongu": "Nachi → Hongū"}[pair]
        last = f"A · {name}: {O['len'] / 1000:.1f} km, ↑ {O['up']} m, ↓ {O['down']} m · heights ×10"
        if pv.get("last") != last or pv.get("ve") != "10.00":
            gate.err("fieldnotes", f"profile of {pair}: shows “{pv.get('last')}” at ×{pv.get('ve')}, the data gives “{last}” at ×10"); n_bad += 1
    if F.get("strip") != "10.00":
        gate.err("fieldnotes", f"the ride strip is drawn at heights ×{F.get('strip')}, its caption says ×10"); n_bad += 1
    # photographs
    M = {m["file"]: m for m in mreg.get("media", [])}
    T = D["town"]; Fr = D["frames"]["town"]
    for p in T["photos"]:
        for key in ("src", "thumb"):
            f = KANSAI / p[key]
            if not f.exists():
                gate.err("fieldnotes", f"photograph file missing: {p[key]}"); n_bad += 1; continue
            try:
                from PIL import Image
                if Image.open(f).getexif():
                    gate.err("fieldnotes", f"{p[key]} still carries EXIF metadata (location must not be published in the file)"); n_bad += 1
            except Exception as e:
                gate.err("fieldnotes", f"{p[key]} could not be opened: {e}"); n_bad += 1
        r = M.get(p["src"])
        if not r or not r.get("own") or not r.get("licence") or not r.get("shows"):
            gate.err("fieldnotes", f"{p['src']} is not registered in media.toml as our own photograph (own = true, licence, shows)"); n_bad += 1
        if not (Fr[0] <= p["x"] <= Fr[2] and Fr[1] <= p["y"] <= Fr[3]):
            gate.err("fieldnotes", f"photograph {p['id']} is placed outside the town frame"); n_bad += 1
        # the time shown with each photograph is the one its file name took from EXIF (img/field/YYYYMMDD_HHMMSS.jpg)
        mt = re.search(r"/(\d{8})_(\d{2})(\d{2})\d{2}\.jpg$", p["src"])
        if not mt or f"{mt.group(2)}:{mt.group(3)}" != p.get("time") or mt.group(1) != "20250928":
            gate.err("fieldnotes", f"photograph {p['id']}: time {p.get('time')} does not match its file {p['src']}"); n_bad += 1
        if p.get("brg") is not None and not (0 <= p["brg"] < 360):
            gate.err("fieldnotes", f"photograph {p['id']}: bearing {p['brg']} outside 0–359°"); n_bad += 1
    # town labels on their references
    P = pts_ref.get("points", {})
    for lab in T.get("labels", []):
        ref = P.get(lab["key"])
        if not ref:
            gate.err("fieldnotes", "town label has no reference in points.toml", lab["key"]); n_bad += 1; continue
        want = tm.to_svg(ref["lon"], ref["lat"], fn_origin())
        d = math.dist(want, (lab["x"], lab["y"])) * 100
        if d > ref.get("tol_m", 60):
            gate.err("fieldnotes", f"{lab['key']} is drawn {d:.0f} m from its reference (tolerance {ref.get('tol_m', 60)} m)"); n_bad += 1
    if not n_bad:
        gate.ok("fieldnotes", f"route tables of {len(D['region']['options'])} pairs and their profiles follow the data; {len(T['photos'])} photographs registered, without metadata, in the town; {len(T.get('labels', []))} town labels on their references")


def fn_origin():
    return [-69782.048, -171691.754]


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
        if key.startswith(("kmk_", "kmc_", "fn_")):
            continue
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


def check_kmk(gate, pts_ref, g, html):
    """Kamikura micro-study: every label sits at its sourced place, the drawn study area and building count match the
    statistics the text quotes, and every file the section loads or offers exists."""
    import os
    try:
        K = kmk_data()
    except Exception as e:
        gate.err("kamikura", f"kansai/data/kamikura.js could not be read: {e}"); return
    P = pts_ref.get("points", {}); n0 = len(gate.errors)
    for lab in K["pts"]:
        key, x, y = "kmk_" + lab[0], lab[2], lab[3]
        if key not in P:
            gate.err("kamikura", f"map label “{lab[1]}” has no sourced reference ({key}) in points.toml", key); continue
        ref = P[key]
        if not ref.get("source"):
            gate.err("kamikura", "no source", key); continue
        off = math.dist(tm.to_svg(ref["lon"], ref["lat"], g["origin"]), (x, y)) * 100
        if off > ref["tol_m"]:
            gate.err("kamikura", f"label “{lab[1]}” is {off:.0f} m from its reference ({ref['source']}); tolerance {ref['tol_m']} m", key)
    for key in P:
        if key.startswith("kmk_") and key[4:] not in {lab[0] for lab in K["pts"]}:
            gate.warn("kamikura", "reference point not used by the micro-study (stale entry?)", key)
    # the town figure of the religious flows: every place it draws sits at its sourced coordinate
    T = K.get("ground", {}).get("sacred", {}).get("town")
    if T:
        X0, Y1 = T["origin"]
        derived = {"confluence", "kumano_lab", "abreast_hay", "abreast_mif"}     # computed from the river's centre line
        for key, (x, y) in T["places"].items():
            if key in derived:
                continue
            ref = P.get("kmc_" + key)
            if not ref or not ref.get("source"):
                gate.err("kamikura", f"town figure place “{key}” has no sourced reference (kmc_{key}) in points.toml", key); continue
            E, N = tm.forward(ref["lon"], ref["lat"])
            off = math.dist((E - X0, Y1 - N), (x, y))
            if off > ref["tol_m"]:
                gate.err("kamikura", f"town figure place “{key}” is {off:.0f} m from its reference ({ref['source']}); tolerance {ref['tol_m']} m", key)
        for key in P:
            if key.startswith("kmc_") and key[4:] not in T["places"]:
                gate.warn("kamikura", "reference point not used by the town figure (stale entry?)", key)
    area = shoelace_m2(K["layers"]["poly"]) / 1e4
    if abs(area - K["stats"]["area_ha"]) > 0.01:
        gate.err("kamikura", f"the drawn study area is {area:.3f} ha but the statistics say {K['stats']['area_ha']} ha")
    nb = len(rings(K["layers"]["b_in"]))
    if nb != K["stats"]["bld_n"]:
        gate.err("kamikura", f"{nb} building outlines are drawn inside the study area but the statistics say {K['stats']['bld_n']}")
    data_dir = Path(os.environ.get("KANSAI_DATA", KANSAI / "data"))
    files = set(re.findall(r'(?:href|src)="(data/kamikura[^"]+)"', html)) | {"data/kamikura.js", K["img"]["href"]}
    files |= {b["href"] for b in K.get("bases", {}).values()}               # the ground layers the switcher loads
    for f in sorted(files):
        if not (data_dir / f.split("/", 1)[1]).exists():
            gate.err("kamikura", f"{f} is referenced by the page but missing")
    if len(gate.errors) == n0:
        gate.ok("kamikura", f"{len(K['pts'])} labels at their sourced places; drawn area {area:.2f} ha and {nb} buildings match the text; data files present")


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


CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
LATIN = re.compile(r"[A-Za-z]{3,}")


def check_links(gate, reg, seen, media_sources=()):
    """Every external link is registered; a plan is always named in Japanese and English next to its link.
    Photo credits link to their source pages, which media.toml registers."""
    R = {l["url"]: l for l in reg.get("link", [])}
    for u in media_sources:
        R.setdefault(u, {"url": u, "kind": "photo", "checked": "media.toml"})
    for l in reg.get("link", []):
        for k in ("url", "kind", "checked"):
            if not l.get(k):
                gate.err("links", f"register entry lacks {k}", l.get("url", "?"))
        if l.get("kind") == "plan" and not (l.get("ja") and l.get("en")):
            gate.err("links", "plan entries need both ja and en titles", l["url"])
    used = set()
    for a in seen:
        u = a["href"]
        used.add(u)
        if u not in R:
            gate.err("links", f"link “{a['text'][:60]}” → {u} is not in links.toml"); continue
        own = a["text"] if (CJK.search(a["text"]) and LATIN.search(a["text"])) else a["block"]
        if R[u].get("kind") == "plan" and not (CJK.search(own) and LATIN.search(own)):
            gate.err("links", f"plan link “{a['text'][:60]}” is not named in both Japanese and English where it appears", u)
    for u in R:
        if u not in used and R[u].get("kind") != "photo":
            gate.warn("links", "registered link no longer used on the page", u)
    if not any(e[0] == "links" for e in gate.errors):
        gate.ok("links", f"{len(used)} external links registered; plans named in Japanese and English")


HTML_CACHE = {}


def page_media(html):
    HTML_CACHE["html"] = html
    m = re.search(r'<script type="application/json" id="media-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else []


OPEN_LICENCES = ("CC BY", "CC BY-SA", "CC0", "Public domain", "PD", "GSI", "Government of Japan Standard Terms of Use", "政府標準利用規約")


def check_media(gate, reg, media):
    """Every picture is a registered file with a source, an author and an open licence, credited as registered."""
    R = {m["file"]: m for m in reg.get("media", [])}
    n = 0
    for item in media:
        for im in item.get("images", []):
            n += 1
            src = im.get("src", "")
            f = KANSAI / src
            if not f.exists():
                gate.err("media", f"image file missing: {src}", item.get("id")); continue
            r = R.get(src)
            if not r:
                gate.err("media", f"{src} is not registered in media.toml", item.get("id")); continue
            for k in ("source", "author", "licence", "licence_url", "shows"):
                if not r.get(k):
                    gate.err("media", f"media.toml entry lacks {k}", src)
            if r.get("licence") and not any(r["licence"].startswith(x) for x in OPEN_LICENCES):
                gate.err("media", f"licence “{r['licence']}” is not an open licence the page may use", src)
            cr = re.sub(r"<[^>]+>", "", im.get("credit", ""))
            if r.get("author") and r["author"] not in cr:
                gate.err("media", f"credit line does not name the author “{r['author']}”", src)
            if r.get("licence") and r["licence"] not in cr:
                gate.err("media", f"credit line does not state the licence “{r['licence']}”", src)
            if im.get("url") != r.get("source"):
                gate.err("media", "the picture's source link differs from the register", src)
    # pictures placed directly in the text: same rules, and the credit must sit in the picture's own caption
    for fig in re.findall(r'<figure[^>]*>(.*?)</figure>', HTML_CACHE.get("html", ""), re.S):
        for src in re.findall(r'<img[^>]+src="(img/[^"]+)"', fig):
            n += 1
            r = R.get(src)
            if not (KANSAI / src).exists():
                gate.err("media", f"image file missing: {src}"); continue
            if not r:
                gate.err("media", f"{src} is not registered in media.toml"); continue
            cap = re.sub(r"<[^>]+>", "", fig)
            if r.get("author") not in cap or r.get("licence") not in cap:
                gate.err("media", "the caption does not credit the registered author and licence", src)
            if r.get("source") and r["source"] not in fig:
                gate.err("media", "the caption does not link the registered source", src)
    files = {p.relative_to(KANSAI).as_posix() for p in (KANSAI / "img").glob("*") if p.is_file()} if (KANSAI / "img").exists() else set()
    used = {im.get("src") for it in media for im in it.get("images", [])} | set(re.findall(r'<img[^>]+src="(img/[^"]+)"', HTML_CACHE.get("html", "")))
    for f in sorted(files - used):
        gate.warn("media", "image file not used by the page", f)
    if not any(e[0] == "media" for e in gate.errors):
        gate.ok("media", f"{n} pictures: files present, sources, authors and open licences registered and credited")


def check_tiles(gate, tiles, g):
    """Imagery tiles land where the QA's own projection says their corners are, and stay affine to < ½ pixel."""
    worst, worst_res = 0.0, 0.0
    for t in tiles:
        z, x, y, m = t["z"], t["x"], t["y"], t["m"]
        n = 2 ** z
        def ll(tx, ty): return tx / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
        nw, ne, sw, se = (tm.to_svg(*ll(*c), g["origin"]) for c in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)))
        a, b, c, d, e, f = m
        got = {"nw": (e, f), "ne": (e + 256 * a, f + 256 * b), "sw": (e + 256 * c, f + 256 * d)}
        for k, want in (("nw", nw), ("ne", ne), ("sw", sw)):
            worst = max(worst, math.dist(got[k], want))
        pred_se = (e + 256 * (a + c), f + 256 * (b + d))
        px = math.dist(nw, ne) / 256
        worst_res = max(worst_res, math.dist(pred_se, se) / px)
    if not tiles:
        gate.err("tiles", "the render report has no tile samples"); return
    if worst * 100 > 0.1:
        gate.err("tiles", f"tile corners are {worst * 100:.3f} m from where tm.py puts them")
    if worst_res > 0.5:
        gate.err("tiles", f"affine tiles bend by {worst_res:.2f} px at the far corner (limit 0.5 px)")
    if not any(e[0] == "tiles" for e in gate.errors):
        gate.ok("tiles", f"{len(tiles)} imagery tiles (z11–18): corners within {worst * 100:.4f} m of tm.py, curvature ≤ {worst_res:.3f} px")


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
    check_kmk(gate, pts_ref, g, html)
    mreg = tomllib.loads((HERE / "media.toml").read_text(encoding="utf-8")) if (HERE / "media.toml").exists() else {}
    check_fn(gate, rep, pts_ref, mreg)
    check_links(gate, tomllib.loads((HERE / "links.toml").read_text(encoding="utf-8")), rep.get("links", []), [m["source"] for m in mreg.get("media", []) if str(m.get("source", "")).startswith("http")])
    check_media(gate, mreg, page_media(html))
    check_tiles(gate, rep.get("tiles", []), g)

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
