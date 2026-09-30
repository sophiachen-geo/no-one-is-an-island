# Kansai map data — build pipeline

`kansai/index.html` is a single static page. Its map data (SVG path strings in the projected
coordinates below, label anchors, statistics, the long profile) sits in one inline block between
`/*GEO:BEGIN*/` and `/*GEO:END*/`. These scripts regenerate that block from open data, so every number
quoted on the page can be traced and recomputed.

Run everything from a **scratch directory outside the repo** (raw downloads are ~400 MB):

```bash
pip install shapely numpy scipy pyproj scikit-image pyshp
mkdir -p /tmp/kansai-work && cd /tmp/kansai-work
T=/path/to/no-one-is-an-island/kansai/tools
bash   $T/01_fetch.sh      # SRTM tiles, MLIT KSJ zips, OSM via Overpass
python3 $T/02_terrain.py   # SRTM mosaic → dem1.npy, dem3.npy
python3 $T/03_land.py      # OSM coastline → land.geojson
python3 $T/04_drainage.py  # priority-flood + D8 on 3″ grid, OSM sea mask
python3 $T/05_basin.py     # trace the Kumano basin from the mouth → basin.geojson (~2,365 km²)
python3 $T/06_admin.py     # N03 municipalities/prefectures, basin shares, Higashimuro
python3 $T/07_build.py     # all layers → geo.json (+ zone/hazard overlap stats, drive-time bands)
python3 $T/08_profile.py   # Totsukawa–Kumano long profile → profile.json
python3 $T/10_gsi_dem.py        # GSI DEM5A (5 m) tiles for the old town → gsi_dem5.npy
python3 $T/11_routes_kodo.py --ohechi  # Kumano Kodō: Iseji (Mie KML), Okugake + Ohechi routed on OSM paths
python3 $T/12_hazard_access.py  # tsunami walking distance to dry ground; roads inside landslide zones (+ stats)
python3 $T/13_flows.py          # timber/charcoal flows down the Kitayama and Kumano; schematic sea lanes
python3 $T/14_ichida_basin.py   # digitise MLIT's Ichida-gawa basin map (図-1.2) → ichida/ichida_basin.json
python3 $T/15_ichida_relief.py  # Ichida river line + old-town micro-relief contours (3–40 m)
python3 $T/16_extras.py         # merge 10–15 + extra views/points (pts2.json) into geo.json
python3 $T/09_inject.py         # write geo.json + profile.json into ../index.html
python3 ../qa/run.py            # the QA/QC gate — must pass before anything is published
```

Every named point added in `pts2.json` needs a sourced reference in `kansai/qa/points.toml`, and every
number that reaches the page needs an entry in `kansai/qa/register.toml`; the gate fails otherwise.

## Sources

- MLIT 国土数値情報: N03 administrative areas (1 Jan 2026); A55 urban-planning decisions for Shingū
  (FY2024: 立地適正化計画区域, 居住誘導区域, 都市機能誘導区域, 都市計画区域); A40 tsunami inundation
  assumptions (Wakayama, Mie; 2016 ed.); A31a flood inundation assumptions (Kinki Regional Development
  Bureau, 想定最大規模, 2025); A33 sediment-disaster warning zones (Aug 2025); A38 medical areas (2020).
- © OpenStreetMap contributors (ODbL): coastline, rivers, roads, railway, Kumano Kodō, places, POIs.
- SRTM 1″ (NASA) via AWS Terrain Tiles; GSI DEM5A 5 m laser elevation tiles (old-town relief, walking distances).
- Mie Prefecture 熊野古道伊勢路ナビ (Iseji route KML); MLIT 市田川流域大規模浸水対策計画 (2019, basin map 図-1.2).

## Choices worth knowing

- Projection: JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674); 1 SVG unit = 100 m.
- Two detail levels: generalised layers for the regional sheet, fine layers inside the Shingū window.
- Each prefecture's tsunami model is clipped to its own territory before it is merged.
- Drive time: OSM road classes at 70/45/35/30/25 km/h (motorway → tertiary) from the Shingū Municipal
  Medical Center; reached roads rasterised at 250 m and grown by a 1.2 km catchment. A sketch of reach,
  not a service-area study.
- Kumano Kodō: Nakahechi and Kohechi come from OSM relations; Iseji from Mie Prefecture's 伊勢路ナビ KML
  (official lines, marked All Rights Reserved); Ōmine Okugake and Ohechi are rebuilt by routing along OSM
  paths between documented waypoints (`11_routes_kodo.py`), with a straight leg where no path connects.
- Map points that are not in `07_build.py` live in `pts2.json` (it overrides; e.g. the Nanairo dam and
  Kushimoto were corrected there after the QA points check).
