#!/usr/bin/env python3
"""Fetch every URL in kansai/qa/links.toml and report any that no longer answers.

    python3 kansai/qa/check_links.py            # all links (network)
    python3 kansai/qa/check_links.py --json out.json

A link passes when it answers HTTP 200 (after redirects), or 206 to a ranged request. Some government
servers refuse HEAD or bot user agents, so each URL is tried with GET and a browser-like agent, with retries.
Exit status 1 if any link fails. CI runs this as an advisory step on pull requests and manual QA runs, never
inside a deploy: an outage of a ministry website must not block a publish, but a link that stays broken shows
up in every pull-request run until the register is fixed.
"""
import argparse, json, sys, time, urllib.error, urllib.request
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("needs Python 3.11+ (tomllib)")

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36 no-one-is-an-island-linkcheck"


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-2047", "Accept-Language": "ja,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            last = (e.code, url)
            if e.code in (404, 410):
                break
        except Exception as e:  # timeouts, resets
            last = (0, f"{type(e).__name__}: {e}")
        time.sleep(2 * (i + 1))
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    reg = tomllib.loads((HERE / "links.toml").read_text(encoding="utf-8"))
    bad, rows = [], []
    for ln in reg.get("link", []):
        code, where = fetch(ln["url"])
        ok = code in (200, 206)
        rows.append({"url": ln["url"], "status": code, "final": where, "ok": ok})
        print(f"{'ok ' if ok else 'BAD'} {code:>3}  {ln['url']}" + ("" if ok or where == ln["url"] else f"  → {where}"))
        if not ok:
            bad.append(ln["url"])
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(rows) - len(bad)}/{len(rows)} links answer")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
