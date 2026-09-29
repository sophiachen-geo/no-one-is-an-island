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
python3 $T/09_inject.py    # write geo.json + profile.json into ../index.html
```

## Sources

- MLIT 国土数値情報: N03 administrative areas (1 Jan 2026); A55 urban-planning decisions for Shingū
  (FY2024: 立地適正化計画区域, 居住誘導区域, 都市機能誘導区域, 都市計画区域); A40 tsunami inundation
  assumptions (Wakayama, Mie; 2016 ed.); A31a flood inundation assumptions (Kinki Regional Development
  Bureau, 想定最大規模, 2025); A33 sediment-disaster warning zones (Aug 2025); A38 medical areas (2020).
- © OpenStreetMap contributors (ODbL): coastline, rivers, roads, railway, Kumano Kodō, places, POIs.
- SRTM 1″ (NASA) via AWS Terrain Tiles.

## Choices worth knowing

- Projection: JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674); 1 SVG unit = 100 m.
- Two detail levels: generalised layers for the regional sheet, fine layers inside the Shingū window.
- Each prefecture's tsunami model is clipped to its own territory before it is merged.
- Drive time: OSM road classes at 70/45/35/30/25 km/h (motorway → tertiary) from the Shingū Municipal
  Medical Center; reached roads rasterised at 250 m and grown by a 1.2 km catchment. A sketch of reach,
  not a service-area study.
- Ōmine Okugake, Iseji and Ohechi are only partly mapped in OSM, so they are drawn as approximate
  courses through waypoints (listed in `07_build.py`); Nakahechi and Kohechi come from OSM relations.
