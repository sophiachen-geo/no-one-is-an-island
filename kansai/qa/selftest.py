#!/usr/bin/env python3
"""Self-test for the QA gate: plant known faults and make sure run.py catches every one.

    python3 kansai/qa/selftest.py [--report render.json]   (without --report it runs check_render.mjs once)

A gate that silently stopped checking would look exactly like a gate that passes. Each case below
copies the page (and the render report) into a temp dir, injects one fault, runs the gate and asserts
that it fails with the expected error category — and that the untouched baseline passes.
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "index.html"
CAVEATS = HERE.parent / "CAVEATS.md"


def gate(page, report, caveats):
    out = Path(tempfile.mkdtemp()) / "result.json"
    r = subprocess.run([sys.executable, str(HERE / "run.py"), "--page", str(page), "--report", str(report),
                        "--caveats", str(caveats), "--json", str(out)], capture_output=True, text=True)
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"errors": [["crash", r.stderr[-400:], ""]]}
    return r.returncode, {e[0] for e in res["errors"]}, res["errors"]


def with_geo(html, fn):
    m = re.search(r"/\*GEO:BEGIN\*/(.*?)/\*GEO:END\*/", html, re.S)
    g = json.loads(m.group(1)); fn(g)
    return html[:m.start(1)] + json.dumps(g, ensure_ascii=False, separators=(",", ":")) + html[m.end(1):]


def main():
    tmp = Path(tempfile.mkdtemp())
    if "--report" in sys.argv:            # reuse the render report CI already produced
        report = Path(sys.argv[sys.argv.index("--report") + 1])
    else:
        report = tmp / "render.json"
        r = subprocess.run(["node", str(HERE / "check_render.mjs"), str(PAGE), str(report)], capture_output=True, text=True)
        if r.returncode or not report.exists():
            sys.exit("could not produce a render report:\n" + r.stdout + r.stderr)
    base_html = PAGE.read_text(encoding="utf-8")
    base_rep = json.loads(report.read_text(encoding="utf-8"))

    def case(name, expect, html=None, rep=None, cav=None):
        d = Path(tempfile.mkdtemp())
        (d / "index.html").write_text(html or base_html, encoding="utf-8")
        (d / "render.json").write_text(json.dumps(rep or base_rep, ensure_ascii=False), encoding="utf-8")
        (d / "CAVEATS.md").write_text(cav if cav is not None else CAVEATS.read_text(encoding="utf-8"), encoding="utf-8")
        code, cats, errs = gate(d / "index.html", d / "render.json", d / "CAVEATS.md")
        ok = (code == 0 and not cats) if expect is None else (code != 0 and any(c.startswith(expect) for c in cats))
        print(f"  {'✓' if ok else '✗'} {name:48s} → {'passes' if code == 0 else 'fails: ' + ', '.join(sorted(cats))}")
        if not ok:
            for e in errs[:5]:
                print("      ", e)
        return ok

    results = []
    print("QA gate self-test")
    results.append(case("baseline (untouched page) passes", None))
    rep = json.loads(json.dumps(base_rep)); rep["inventory"].append({"src": "p#steps", "text": "The city has 31,000 residents."})
    results.append(case("an unsourced number is caught", "unsourced-number", rep=rep))
    rep = json.loads(json.dumps(base_rep)); rep["inventory"].append({"src": "p#steps", "text": "Floods came seven times a year."})
    results.append(case("an unsourced number word is caught", "unsourced-number", rep=rep))
    rep = json.loads(json.dumps(base_rep))
    rep["inventory"] = [dict(it, text=it["text"].replace("2,968", "2,964")) for it in rep["inventory"]]
    results.append(case("a claim edited on the page (2,968→2,964) is caught", "stale-claim", rep=rep))
    html = with_geo(base_html, lambda g: g["stats"]["ls_roads"]["NR168"].__setitem__("pct", 27.0))
    results.append(case("data no longer matching the text (20%→27%) is caught", "derived", html=html))
    html = with_geo(base_html, lambda g: g["pts"].__setitem__("hayatama", [g["pts"]["hayatama"][0] + 5, g["pts"]["hayatama"][1]]))
    results.append(case("a map point moved 500 m is caught", "points", html=html))
    rep = json.loads(json.dumps(base_rep)); rep["usedPoints"].append("dam_sakamoto")
    results.append(case("a map point without a sourced reference is caught", "points", rep=rep))
    rep = json.loads(json.dumps(base_rep)); rep["errors"].append({"check": "label-overlap", "msg": "A ⟷ B", "where": "desktop step 3"})
    results.append(case("a render failure blocks the gate", "render/", rep=rep))
    results.append(case("a hand-edited CAVEATS.md is caught", "caveats", cav=CAVEATS.read_text(encoding="utf-8") + "\n- sneaky edit\n"))
    # links: every external link registered; a plan always named in Japanese and English
    rep = json.loads(json.dumps(base_rep)); rep["links"].append({"href": "https://example.com/plan.pdf", "text": "a plan", "block": "a plan"})
    results.append(case("an unregistered link is caught", "links", rep=rep))
    rep = json.loads(json.dumps(base_rep)); rep["links"].append({"href": "https://www.city.shingu.lg.jp/Info/773", "text": "the plan", "block": "see the plan"})
    results.append(case("a plan named only in English is caught", "links", rep=rep))
    # imagery: a tile placed half a unit (50 m) off
    rep = json.loads(json.dumps(base_rep)); rep["tiles"][0]["m"][4] += 0.5
    results.append(case("a misplaced imagery tile is caught", "tiles", rep=rep))
    # buildings: one footprint moved into the sea changes a count the text relies on
    def data_copy():
        d = Path(tempfile.mkdtemp())
        for f in list((HERE.parent / "data").glob("kamikura*")) + [HERE.parent / "data" / "fieldnotes.js", HERE.parent / "data" / "risk.js"]:
            shutil.copy(f, d / f.name)
        return d
    ddir = data_copy(); raw = (HERE.parent / "data" / "buildings.js").read_text(encoding="utf-8").strip()
    B = json.loads(raw[raw.index("=") + 1:].rstrip(";")); B["counts"]["total"] -= 1
    (ddir / "buildings.js").write_text("window.__BLD=" + json.dumps(B, separators=(",", ":")) + ";", encoding="utf-8")
    import os
    os.environ["KANSAI_DATA"] = str(ddir)
    results.append(case("building data that no longer matches is caught", "derived"))
    # Kamikura micro-study: a statistic that drifts from the text, and a label moved 50 m off its sourced place
    def kmk_case(name, expect, edit):
        d = data_copy(); shutil.copy(HERE.parent / "data" / "buildings.js", d / "buildings.js")
        raw = (d / "kamikura.js").read_text(encoding="utf-8").strip(); K = json.loads(raw[raw.index("=") + 1:].rstrip(";")); edit(K)
        (d / "kamikura.js").write_text("window.__KMK=" + json.dumps(K, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
        os.environ["KANSAI_DATA"] = str(d)
        return case(name, expect)
    results.append(kmk_case("Kamikura data that drifts from the text is caught", "derived", lambda K: K["stats"].update(area_ha=K["stats"]["area_ha"] + 0.4)))
    results.append(kmk_case("a Kamikura label moved off its place is caught", "kamikura", lambda K: K["pts"][6].__setitem__(2, K["pts"][6][2] + 0.5)))
    # the ground section: a measured slope that drifts from the text, and a ground layer the switcher cannot load
    results.append(kmk_case("a drifting ground measurement is caught", "derived", lambda K: K["ground"]["foot"].update(up_deg=33.0)))
    # comparing gazes: a coded count that no longer matches the figure drawn from it
    results.append(kmk_case("a gaze count out of step with its figure is caught", "gaze", lambda K: K["gaze"]["rows"][0]["pos"].__setitem__(1, 6)))
    d = data_copy(); shutil.copy(HERE.parent / "data" / "buildings.js", d / "buildings.js"); (d / "kamikura_lrm.jpg").unlink()
    os.environ["KANSAI_DATA"] = str(d)
    results.append(case("a missing ground layer is caught", "kamikura"))
    # field notes: a statistic that drifts from the text, a photograph shown at the wrong time, a route table out of step
    def fn_case(name, expect, edit):
        d = data_copy(); shutil.copy(HERE.parent / "data" / "buildings.js", d / "buildings.js")
        raw = (d / "fieldnotes.js").read_text(encoding="utf-8").strip(); D = json.loads(raw[raw.index("=") + 1:].rstrip(";")); edit(D)
        (d / "fieldnotes.js").write_text("window.__FN=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        os.environ["KANSAI_DATA"] = str(d)
        return case(name, expect)
    results.append(fn_case("field-notes data that drifts from the text is caught", "derived", lambda D: D["stats"]["ride"].update(leg2_channel_m=360)))
    results.append(fn_case("a field photograph shown at the wrong time is caught", "fieldnotes", lambda D: D["town"]["photos"][0].update(time="10:38")))
    exif = Path(tempfile.mkdtemp()) / "20250928_103732.jpg"     # a JPEG whose header still holds an EXIF block
    exif.write_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00MM\x00\x2a\x00\x00\x00\x08\xff\xd9")
    results.append(fn_case("a photograph that still carries EXIF is caught", "fieldnotes", lambda D: D["town"]["photos"][0].update(src=str(exif))))
    results.append(fn_case("a route table out of step with its data is caught", "fieldnotes",
                           lambda D: D["region"]["options"]["hongu-hayatama"]["list"][0].update(up=D["region"]["options"]["hongu-hayatama"]["list"][0]["up"] + 5)))
    # the risk analysis: a table cell and a sentence that drift from kansai/data/risk.js
    def rk_case(name, expect, edit):
        d = data_copy(); shutil.copy(HERE.parent / "data" / "buildings.js", d / "buildings.js")
        raw = (d / "risk.js").read_text(encoding="utf-8").strip(); R = json.loads(raw[raw.index("=") + 1:].rstrip(";")); edit(R)
        (d / "risk.js").write_text("window.__RISK = " + json.dumps(R, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        os.environ["KANSAI_DATA"] = str(d)
        return case(name, expect)
    results.append(rk_case("a risk table cell out of step with its data is caught", "risk", lambda R: R["stats"]["tiers"]["Kiho"]["fl_l2"].update(people=3500)))
    results.append(rk_case("risk data that drifts from the text is caught", "derived", lambda R: R["stats"]["ev_ouji"].update(fail_W_DH_5=44)))
    del os.environ["KANSAI_DATA"]
    # pictures: a picture whose file does not exist
    html = base_html.replace('<script type="application/json" id="media-data">', '<script type="application/json" id="media-data">', 1)
    m = re.search(r'(<script type="application/json" id="media-data">)(.*?)(</script>)', html, re.S)
    media = json.loads(m.group(2)); media.append({"id": "ghost", "pt": "castle", "groups": "heritage", "title": "Ghost", "images": [{"src": "img/ghost.jpg", "w": 10, "h": 10, "alt": "", "caption": "", "credit": "Photo: nobody, CC BY 4.0"}]})
    html = html[:m.start(2)] + json.dumps(media, ensure_ascii=False) + html[m.end(2):]
    results.append(case("a picture without a registered file is caught", "media", html=html))
    # boxes: the plan diagram that once spilled its label (rendered in Chromium, web fonts on and off)
    syn = Path(tempfile.mkdtemp()) / "box.html"
    syn.write_text('<!doctype html><meta charset="utf-8"><style>body{font-family:"Noto Serif JP",Georgia,serif}.chart text{font-size:10px}</style>'
                   '<figure class="fig chart" style="width:420px"><svg viewBox="0 -5 400 151" aria-label="plan diagram">'
                   '<g><rect x="261.5" y="92" width="138" height="26" rx="3" fill="#f4efe6" stroke="#1d998c"/>'
                   '<text x="330.5" y="109" text-anchor="middle" class="s">Location Optimization Plan (立地適正化計画)</text></g></svg></figure>', encoding="utf-8")
    out = syn.parent / "box.json"
    r = subprocess.run(["node", str(HERE / "check_render.mjs"), str(syn), str(out), "--charts-only"], capture_output=True, text=True)
    caught = out.exists() and any(e["check"] == "text-in-box" for e in json.loads(out.read_text(encoding="utf-8"))["errors"])
    print(f"  {'✓' if caught else '✗'} {'text spilling out of a diagram box is caught':48s} → {'fails: text-in-box' if caught else 'not caught: ' + (r.stderr or r.stdout)[-300:]}")
    results.append(caught)
    shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(results)
    print(f"\n{n_ok}/{len(results)} self-test cases behave as expected")
    sys.exit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
