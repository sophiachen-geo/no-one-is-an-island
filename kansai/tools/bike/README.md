# Field notes · Shingū’s three shrines by bicycle

Builds `kansai/data/fieldnotes.js` (`window.__FN`): our ride of 28 September 2025 through Shingū, placed by our
photographs; walking, cycling and driving detours from every building of the town core; and the bicycle-legal
routes between 熊野本宮大社, 熊野速玉大社 and 熊野那智大社 with their road-bed profiles, hazards and rain closures.

Run from a work directory `<work>/bike`, with the main build’s `geo/` (`ksj/`, `osm/places.json`,
`kmk/gsi_water.geojson`), the photographs’ `photos/` (from `../photos/ingest.py`) and the downloaded lists in
`research/bike/` beside it (or point `BIKE_RESEARCH` / `KANSAI_KSJ` elsewhere):

```bash
T=/path/to/no-one-is-an-island/kansai/tools/bike
python3 $T/fetch_tiles.py      # OSM highways, 33.60–33.90 N × 135.70–136.06 E, in 9 Overpass tiles → roads.json
                               #   (fetch22.py splits a tile that times out); check timestamp_osm_base: use a fresh mirror
python3 $T/run_plateau.py 1.6  # plateau alternatives (plateau.py, stretch 1.6) between the shrines, on the
                               #   bicycle-legal graph of route.py (no motorway, motorroad, bicycle=no, foot-only ways)
python3 $T/corridors.py        # union of the alternatives → chains between junctions (chains.json)
python3 $T/build_corr.py       # per chain: length, road-bed heights (metrics.py, benchdp.py on GSI DEM via dem.py),
                               #   climb with 5 m hysteresis, tunnels and bridges, refs, surfaces (corridors.json)
python3 $T/run_haz.py          # metres in A33 landslide zones, A40 tsunami (L2) and A31a flood areas (hazards.py)
python3 $T/region_gsi.py       # GSI road category and width class per chain (optimal_bvmap-v1 z16, RdCL)
python3 $T/pcr.py              # metres on the 太平洋岸自転車道 (overlap with MLIT's KML; the line is not exported)
python3 $T/validate_final.py   # road bed vs GSI benchmarks and spot heights within 15 m (gsi_pts.py) → validate_final.json
python3 $T/town_fetch.py       # town core: GSI vector tiles z16 and OSM shops, amenities, worship, water
python3 $T/export_fn.py        # region: chains, nodes, route families per pair (options.py) → fn_region.json
python3 $T/export_misc.py      # photographs (true-north headings, captions) and motorways → fn_misc.json
python3 $T/closures.py         # rain-closure sections of Wakayama and Mie on the network and the chains
python3 $T/export_town.py      # runs town.py (three networks, detours, the ride coded every 20 m) → fn_town.json
python3 $T/write_fn.py /path/to/no-one-is-an-island/kansai   # → data/fieldnotes.js, with every number the text quotes
python3 /path/to/no-one-is-an-island/kansai/qa/run.py          # the gate re-checks them ("fn" claims, check_fn)
```

Photographs: `../photos/ingest.py <orig> <web>` reads EXIF (time, position, heading, accuracy) into
`manifest.json`; `../photos/publish.py <photos> <kansai/img/field>` writes the page’s copies without metadata.

## Choices worth knowing

- **Legality.** Bicycles are 軽車両 under the Road Traffic Act: every road but motorways and 自動車専用道路
  (`highway=motorway`, `motorroad=yes`), ways signed `bicycle=no`, and foot-only ways unless OSM admits bicycles.
  那智勝浦新宮道路 and 新宮紀宝道路 are motorways in OSM.
- **Heights.** GSI 標高タイル, DEM5A first (5B, 5C, 10B where 5A is missing), every 20 m. A mapped line can sit metres
  off the road; on a slope that is metres of height, so the road bed is tracked as the flattest ground within 15 m
  across the line (Viterbi, `benchdp.py`); tunnels and bridges are interpolated between their ends. Checked on 44
  GSI points: median error 0.25 m. The worst (13.8 m) and the one grade the page withholds (61 % over 200 m) lie on
  県道45 below 高瀬峠, where OSM draws an unpaved line straight up the slope.
- **Route families.** All simple paths on the chain graph up to 1.6 × the shortest, grouped by the long chains
  (≥ 2 km) they use; the shortest of each family is listed.
- **Rain closures.** Wakayama’s sections come with start and end points; Mie’s by place names only. A Mie section
  that is a whole road runs between the road’s ends (小船紀宝線); otherwise between GSI place annotations or OSM
  place nodes (Route 311 矢ノ川–小栗須: 2.3 km drawn for Mie’s 1.1 km; 御浜紀和線 阿田和–上野: 10.3 km for 9.8 km).
  A route “closes” at the lowest threshold of the sections it follows for 200 m or more. MLIT has no section on
  Route 42 in this area.
- **Hazards.** A40 is still Wakayama’s 2013 and Mie’s 2015 tsunami assumption; both prefectures published new
  ones in March 2026 as PDF maps only. Swap the layer when GIS data appears.
- **Town.** Directness = (access + network + access) ÷ straight line, to 260 fixed destinations 150–800 m away
  (seed 20250928), access ≤ 60 m, at least 8 trips per building. Driving uses GSI width classes of 3 m or more.
  The ride between stops is the shortest bicycle-legal route; only the stops are measured (EXIF, 3.5–12.6 m).
- **Headings.** The phone records magnetic headings (`GPSImgDirectionRef = M`); they are turned to true north with
  the World Magnetic Model 2025 (`pygeomag`), 7.8° W here.
- **Third-party lines.** The Tourist Association’s route line and MLIT’s cycling-road KML are not redistributed;
  only measurements made with them are.

Requires `shapely`, `pyproj`, `numpy`, `scipy`, `pillow`, `mapbox-vector-tile`, `pyshp`, `pygeomag`.
