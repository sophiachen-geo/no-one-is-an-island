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
# tsunami2026/: Wakayama's and Mie's 2026 tsunami maps digitised (Shingū, Kihō) + the animation's arrival field — run it
#   before 07_build.py, which reads its polygons from $TSUNAMI2026 (default ./tsunami2026); see tsunami2026/README.md
python3 $T/07_build.py     # all layers → geo.json (+ zone/hazard overlap stats, drive-time bands)
python3 $T/08_profile.py   # Totsukawa–Kumano long profile → profile.json
python3 $T/10_gsi_dem.py        # GSI DEM5A (5 m) tiles for the old town → gsi_dem5.npy
python3 $T/11_routes_kodo.py --ohechi  # Kumano Kodō: Iseji, Okugake and Ohechi routed on OSM paths
python3 $T/12_hazard_access.py  # roads inside landslide zones (+ stats)
python3 $T/13_flows.py          # timber/charcoal flows down the Kitayama and Kumano; schematic sea lanes
python3 $T/14_ichida_basin.py   # digitise MLIT's Ichida-gawa basin map (図-1.2) → ichida/ichida_basin.json
python3 $T/15_ichida_relief.py  # Ichida river line + old-town micro-relief contours (3–40 m)
python3 $T/16_extras.py         # merge 10–15 + extra views/points (pts2.json) into geo.json
python3 $T/fetch_facilities.py  # OSM numbered roads in Shingū City → fac/ (services come from 国土数値情報 in 17_round3.py)
# morph/: see tools/morph/README.md — forest (L03-b), park zones (A10), OSM summits, GSI building footprints
python3 $T/17_round3.py         # per-level contours + height labels, forest/parks/peaks, building exposure
                                #   (→ buildings_page.json, copy to ../data/buildings.js), services (P04, P05, P14, P17, P18, P29), road labels
python3 $T/09_inject.py         # write geo.json + profile.json into ../index.html
# kamikura/: the last chapter's micro-study (1 m relief, study area, transect, alignment test) — see kamikura/README.md
# bike/: field notes · the three shrines by bicycle (routes, road-bed heights, closures, the town's networks) — see bike/README.md
# risk/: residents per building, exposure by tier, evacuation margins, the plan's zones, roads under hazard, 2050 → ../data/risk.js — see risk/README.md
python3 ../qa/run.py            # the QA/QC gate — must pass before anything is published
```

Every named point added in `pts2.json` needs a sourced reference in `kansai/qa/points.toml`, and every
number that reaches the page needs an entry in `kansai/qa/register.toml`; the gate fails otherwise.

## Sources

- MLIT 国土数値情報: N03 administrative areas (1 Jan 2026); A55 urban-planning decisions for Shingū
  (FY2024: 立地適正化計画区域, 居住誘導区域, 都市機能誘導区域, 都市計画区域); A40 tsunami inundation
  assumptions (Wakayama, Mie; 2016 ed.; replaced inside Shingū and Kihō by the 2026 maps, see tsunami2026/);
  A31b flood meshes (2025: every national and prefectural river with a map, planned scale, maximum, duration,
  house-collapse zones) and the A31a map of the Ichida-gawa; A33 sediment-disaster warning zones (Aug 2025);
  A38 medical areas (2020); P04 medical institutions (2020), P05 town offices (2022), P14 welfare facilities
  (2023), P17 fire and P18 police stations (2012), P29 schools (2023).
- © OpenStreetMap contributors (ODbL): coastline, rivers, roads, railway, Kumano Kodō, places, POIs.
- SRTM 1″ (NASA) via AWS Terrain Tiles; GSI DEM5A 5 m laser elevation tiles (old-town relief, ground heights).
- GSI 電子国土基本図 place names (experimental_anno tiles): the Iseji's passes and villages; MLIT 市田川流域大規模浸水対策計画
  (2019, basin map 図-1.2).

## Choices worth knowing

- Projection: JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674); 1 SVG unit = 100 m.
- Two detail levels: generalised layers for the regional sheet, fine layers inside the Shingū window.
- Each prefecture's tsunami model is clipped to its own territory before it is merged; inside Shingū and Kihō the
  2026 maps replace A40.
- Drive time: OSM road classes at 70/45/35/30/25 km/h (motorway → tertiary) from the Shingū Municipal
  Medical Center; reached roads rasterised at 250 m and grown by a 1.2 km catchment. A sketch of reach,
  not a service-area study.
- Kumano Kodō: Nakahechi and Kohechi come from OSM relations. Iseji, Ōmine Okugake and Ohechi are rebuilt by
  routing along OSM paths between documented waypoints (`11_routes_kodo.py`), with a straight leg where no path
  connects. The Iseji's waypoints are the passes and villages GSI's base map names along the course (Mie Prefecture's
  section names fix it; its route lines are All Rights Reserved and are not used), its 浜街道 the OSM coastline of
  七里御浜 as far as 井田. Against a local copy of Mie's lines (`--check-mie`, not redistributed) the rebuilt Iseji lies a median
  10 m away, 69% within 100 m and 98% within 500 m (1 October 2026); the 荷坂峠 variant is not drawn.
- Map points that are not in `07_build.py` live in `pts2.json` (it overrides; e.g. the Nanairo dam and
  Kushimoto were corrected there after the QA points check).
