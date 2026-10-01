#!/usr/bin/env bash
# Download the raw inputs for the Kansai / Shingū maps into the CURRENT directory (use a scratch
# folder outside the repo — about 400 MB). Re-running skips files that already exist.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

# SRTM 1" tiles (NASA SRTM via AWS Terrain Tiles / Mapzen "skadi")
for t in N33E135 N33E136 N34E135 N34E136; do
  [ -f "$t.hgt" ] || { curl -sfL -o "$t.hgt.gz" "https://s3.amazonaws.com/elevation-tiles-prod/skadi/${t:0:3}/$t.hgt.gz"; gunzip -f "$t.hgt.gz"; }
done

# MLIT National Land Numerical Information (国土数値情報)
KSJ=https://nlftp.mlit.go.jp/ksj/gml/data
mkdir -p ksj && cd ksj
get() { local f; f="$(basename "$1")"; [ -f "$f" ] || curl -sfL -o "$f" "$KSJ/$1"; }
get N03/N03-2026/N03-20260101_30_GML.zip        # administrative areas: Wakayama
get N03/N03-2026/N03-20260101_24_GML.zip        #                        Mie
get N03/N03-2026/N03-20260101_29_GML.zip        #                        Nara
get A55/A55-24/A55-24_30207_GEOJSON.zip         # urban-planning decisions, Shingū (立地適正化計画 zones)
get A40/A40-16/A40-16_30_GML.zip                # tsunami inundation assumption: Wakayama
get A40/A40-16/A40-16_24_GML.zip                #                                Mie
get A31a/A31a-25/A31a-25_86_10_GEOJSON.zip      # flood inundation assumptions, Kinki Regional Development Bureau
get A33/A33-25/A33-25_30_GEOJSON.zip            # sediment-disaster warning zones: Wakayama
get A33/A33-25/A33-25_24_GEOJSON.zip            #                                 Mie
get A38/A38-20/A38-20_30_GML.zip                # medical areas (secondary medical area check)
get A31b/A31b-25/A31b-25_10_5035_SHP.zip        # flood inundation, 10 m mesh, every river with a published map (national: 10,
get A31b/A31b-25/A31b-25_10_5036_SHP.zip        #   prefectural: 20) for first-level meshes 5035 and 5036: planned scale,
get A31b/A31b-25/A31b-25_20_5035_SHP.zip        #   maximum assumed, duration, house-collapse zones
get A31b/A31b-25/A31b-25_20_5036_SHP.zip
get P04/P04-20/P04-20_30_GML.zip                # services in Shingū City: medical institutions (2020)
get P05/P05-22/P05-22_30_GML.zip                #   city offices (2022)
get P29/P29-23/P29-23_30_GML.zip                #   schools (2023)
get P14/P14-23/P14-23_30_GML.zip                #   welfare facilities (2023; Wakayama: non-commercial use)
get P17/P17-12/P17-12_30_GML.zip                #   fire stations (2012, non-commercial)
get P18/P18-12/P18-12_30_GML.zip                #   police stations (2012, non-commercial)
for z in N03-20260101_30_GML N03-20260101_24_GML N03-20260101_29_GML A33-25_30_GEOJSON A33-25_24_GEOJSON; do unzip -o -q "$z.zip" '*.geojson'; done
unzip -o -q A55-24_30207_GEOJSON.zip
unzip -o -q A40-16_30_GML.zip '*.geojson'
unzip -o -q A40-16_24_GML.zip '*.shp' '*.dbf' '*.shx' '*.prj'
unzip -o -q A38-20_30_GML.zip '*.geojson' || true
# Kumano (8606010001), Ichida (…0002) and Onodani (相野谷川, …0006) rivers, maximum-assumed scale
unzip -o -q A31a-25_86_10_GEOJSON.zip '20_*8606010001*' '20_*8606010002*' '20_*8606010006*' || true
python3 - <<'PY'      # the A31b archives store Windows paths (10_計画規模\…): unpack with forward slashes
import zipfile, os
for z in ("A31b-25_10_5035_SHP", "A31b-25_10_5036_SHP", "A31b-25_20_5035_SHP", "A31b-25_20_5036_SHP"):
    with zipfile.ZipFile(z + ".zip") as f:
        for i in f.infolist():
            out = os.path.join("A31b-25", *i.filename.replace("\\", "/").split("/"))
            if i.is_dir(): continue
            os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "wb").write(f.read(i))
PY
cd ..
# 2026 tsunami polygons for Shingū and Kihō: built by tools/tsunami2026 (run.sh), copied into ./tsunami2026

# OpenStreetMap (Overpass)
python3 "$HERE/fetch_osm.py"
python3 "$HERE/fetch_osm.py" --trails   # path networks for the Kumano Kodō courses rebuilt in 11_routes_kodo.py

# Second-round sources (see 10–16)
mkdir -p kodo ichida
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
# MLIT 市田川流域大規模浸水対策計画 (2019) — 図-1.2 市田川流域図 on p. 9 is digitised by 14_ichida_basin.py
curl -sL --max-time 120 -A "$UA" -o ichida/shiryou.pdf "https://www.kkr.mlit.go.jp/kinan/kasen/ichidagawa/k1cog50000000d9i-att/shiryou.pdf"
