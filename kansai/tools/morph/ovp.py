import urllib.request, urllib.parse, time, json, ssl, os, sys
URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
UA = "no-one-is-an-island/1.0"
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")

def overpass(query, cache=None, tries=8, timeout=400):
    if cache and os.path.exists(cache) and os.path.getsize(cache) > 0:
        with open(cache) as f:
            return json.load(f)
    data = urllib.parse.urlencode({"data": query}).encode()
    delay = 10
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(URL, data=data, headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                raw = r.read()
            js = json.loads(raw)
            if "remark" in js and not js.get("elements"):
                print("REMARK:", js["remark"], file=sys.stderr)
            if cache:
                with open(cache, "wb") as f:
                    f.write(raw)
            return js
        except urllib.error.HTTPError as e:
            last = e
            body = e.read()[:300]
            print(f"HTTP {e.code} try {i}: {body!r}", file=sys.stderr)
            if e.code in (429, 504, 502, 503):
                time.sleep(delay); delay = min(delay * 2, 120); continue
            raise
        except Exception as e:
            last = e
            print(f"ERR try {i}: {e!r}", file=sys.stderr)
            time.sleep(delay); delay = min(delay * 2, 120)
    raise RuntimeError(f"overpass failed: {last!r}")
