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
for z in N03-20260101_30_GML N03-20260101_24_GML N03-20260101_29_GML A33-25_30_GEOJSON A33-25_24_GEOJSON; do unzip -o -q "$z.zip" '*.geojson'; done
unzip -o -q A55-24_30207_GEOJSON.zip
unzip -o -q A40-16_30_GML.zip '*.geojson'
unzip -o -q A40-16_24_GML.zip '*.shp' '*.dbf' '*.shx' '*.prj'
unzip -o -q A38-20_30_GML.zip '*.geojson' || true
# Kumano (8606010001), Ichida (…0002) and Onodani (相野谷川, …0006) rivers, maximum-assumed scale
unzip -o -q A31a-25_86_10_GEOJSON.zip '20_*8606010001*' '20_*8606010002*' '20_*8606010006*' || true
cd ..

# OpenStreetMap (Overpass)
python3 "$HERE/fetch_osm.py"

# Second-round sources (see 10–16)
mkdir -p kodo ichida
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
# Mie Prefecture 熊野古道伊勢路ナビ — official Iseji route lines (the file is marked All Rights Reserved; see CAVEATS.md)
curl -sL --max-time 120 -A "$UA" -o kodo/out4utf8h_alpha128.kml "https://www.kodo.pref.mie.lg.jp/navi/assets/kml/out4utf8h_alpha128.kml"
# MLIT 市田川流域大規模浸水対策計画 (2019) — 図-1.2 市田川流域図 on p. 9 is digitised by 14_ichida_basin.py
curl -sL --max-time 120 -A "$UA" -o ichida/shiryou.pdf "https://www.kkr.mlit.go.jp/kinan/kasen/ichidagawa/k1cog50000000d9i-att/shiryou.pdf"
