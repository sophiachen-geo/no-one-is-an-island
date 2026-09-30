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
    html = with_geo(base_html, lambda g: g["stats"]["overlap"]["centre"].__setitem__("either", 79.0))
    results.append(case("data no longer matching the text (86%→79%) is caught", "derived", html=html))
    html = with_geo(base_html, lambda g: g["pts"].__setitem__("hayatama", [g["pts"]["hayatama"][0] + 5, g["pts"]["hayatama"][1]]))
    results.append(case("a map point moved 500 m is caught", "points", html=html))
    rep = json.loads(json.dumps(base_rep)); rep["usedPoints"].append("dam_sakamoto")
    results.append(case("a map point without a sourced reference is caught", "points", rep=rep))
    rep = json.loads(json.dumps(base_rep)); rep["errors"].append({"check": "label-overlap", "msg": "A ⟷ B", "where": "desktop step 3"})
    results.append(case("a render failure blocks the gate", "render/", rep=rep))
    results.append(case("a hand-edited CAVEATS.md is caught", "caveats", cav=CAVEATS.read_text(encoding="utf-8") + "\n- sneaky edit\n"))
    shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(results)
    print(f"\n{n_ok}/{len(results)} self-test cases behave as expected")
    sys.exit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
