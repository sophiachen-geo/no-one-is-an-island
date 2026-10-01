import json, sys, time, urllib.request, urllib.parse
UA = "no-one-is-an-island/kansai-qa (research; contact via github sophiachen-geo)"
EPS = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter",
       "https://overpass.private.coffee/api/interpreter",
       ]
def run(q, out):
    last = None
    for attempt in range(8):
        ep = EPS[attempt % len(EPS)]
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r:
                b = r.read()
            d = json.loads(b)
            if "remark" in d and "error" in d["remark"].lower():
                raise RuntimeError(d["remark"])
            json.dump(d, open(out, "w"))
            print(out, len(d["elements"]), d["osm3s"]["timestamp_osm_base"], ep, file=sys.stderr)
            return d
        except Exception as e:
            last = e
            print("retry", attempt, ep, repr(e)[:200], file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise last
BB = "33.60,135.70,33.90,136.06"
if __name__ == "__main__":
    which = sys.argv[1]
    if which == "roads":
        run(f'[out:json][timeout:600][maxsize:1073741824];way["highway"]["highway"!~"^(proposed|construction|abandoned|platform|raceway|bus_stop|elevator|corridor|via_ferrata|razed|disused)$"]({BB});out body geom qt;', "roads.json")
    elif which == "cycle":
        run(f'[out:json][timeout:300];(relation["route"~"^(bicycle|mtb)$"]({BB});way["highway"="cycleway"]({BB});way["cycleway"]({BB});way["bicycle"]({BB});way["motorroad"]({BB}););out body geom qt;', "cycle.json")
    elif which == "pois":
        run(f'[out:json][timeout:300];(nwr["amenity"~"^(bicycle_rental|bicycle_parking|bicycle_repair_station|drinking_water|toilets)$"]({BB});nwr["shop"="bicycle"]({BB});nwr["tourism"="information"]["information"~"office|visitor_centre"]({BB});nwr["highway"="rest_area"]({BB});nwr["amenity"="fuel"]({BB}););out center tags qt;', "pois.json")
    elif which == "tunnels":
        run(f'[out:json][timeout:300];way["tunnel"]["highway"]({BB});out body geom qt;', "tunnels.json")
