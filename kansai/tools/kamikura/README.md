# Kamikura mountain foot · micro-morphology (last chapter of the Kansai page)

Builds `kansai/data/kamikura.js` (the chapter's map, figures and statistics), the ground layers
`kamikura_{relief,elev,slope,lrm,curv}.jpg` (1 m), and the GIS downloads `kamikura_study.geojson` / `.kml` and
`kamikura_cadastre.geojson`. Run from a work directory beside the main build's (`<work>/kmk`, with the main build's
`morph/` and `ksj/` one level up, and the Ministry of Justice zip for 新宮市 in `moj/`):

```bash
T=/path/to/no-one-is-an-island/kansai/tools/kamikura
python3 $T/01_fetch.py         # GSI DEM1A (1 m) tiles for the frame (DEM5A where 1 m is missing) + every OSM feature in it
python3 $T/02_terrain.py       # 1 m grid in JGD2011 / CS VI, slope, the break of slope and the line 25 m upslope of it
python3 $T/03_study.py         # study polygon, transect, statistics (→ study.json)
python3 $T/05_terrain_plus.py  # which DEM the ground can bear (coverage, benchmarks, DEM5A), local relief, curvature
python3 $T/06_foot.py          # the mountain foot, four ways, on cross-profiles every 2 m (→ foot.json)
python3 $T/07_parcels.py       # the MoJ parcel map (任意座標系) registered to GSI road edges (→ parcels.json)
python3 $T/08_align.py         # what follows the foot: eight feature classes, six runs (→ align.json, walls.json, …)
python3 $T/09_export.py /path/to/no-one-is-an-island/kansai   # page data, ground layers, GeoJSON/KML
python3 /path/to/no-one-is-an-island/kansai/qa/run.py          # the gate re-checks every number and label
```

`gsi.py` reads GSI's optimal vector tiles (road edges, water edges, buildings, benchmarks); `mojparse.py` reads the
Ministry of Justice 地図XML.

## The study area: four rules

| edge  | rule | data |
|-------|------|------|
| west  | 25 m (horizontal) upslope of the break of slope | GSI DEM1A |
| east  | the street bounding the 神倉小学校 compound, continued south on the same line | OSM 121367848 · 1031510641 · 121367953 |
| north | the lane closing the first full block above the school and the temple row | OSM 266991552 · 121369902 |
| south | the street just south of the shrine-entrance cluster, carried west across the foot of the steps | OSM 121367975 · 121370515 · 499568826 |

Break of slope: the edge of ground at least 1 m above the plain (median of near-flat ground) that is steeper than
12° or more than 3 m above the plain, connected to the slopes above 40 m; small spurs removed (opening, r = 2 m).

## Where the mountain stops (05, 06)

- Every cell of the study area is DEM1A. The audit compares it with GSI's levelling benchmarks and triangulation
  points (vector-tile symbol layer) and with DEM5A, which agrees on flat open ground but loses most of the channel's
  depth. 31% of the area is under buildings, where DEM1A is interpolated.
- Local relief = ground minus its Gaussian-smoothed surface (σ 8 m). Profile and plan curvature are computed on ground
  smoothed with σ 2.5 m; negative profile curvature = concave (a foot).
- The foot is found on 310 cross-profiles (every 2 m, perpendicular to the front smoothed over 41 m, 40 m upslope to
  60 m out) as (A) the mask edge, (B) the first point 1 m above the profile's own plain, (C) the most concave point
  between the plain and 10 m above it, (D) the knee of a two-segment fit. The consensus is their median.

## The parcel map (07)

The sheet 「新宮・千穂一丁目・神倉一丁目他」 is in arbitrary coordinates, digitised from cadastral drawings. Its roads
(道) and waterways (水) are parcels. The fragment holding 千穂一丁目 is placed by matching the school parcel
(715-3) to the school's OSM outline, then by fitting its road parcels to GSI road edges (truncated chamfer distance;
similarity, then affine). The drawing must be enlarged 13–16% (縄伸び) and turned about 14°; road parcels then sit a
median 1.2 m from the road edges. Parcel numbers are not published in the download.

## What follows the foot (08)

Each feature is cut into pieces of at most 10 m. Only pieces where the local foot direction (±10 m) and the town
grid (GSI road edges > 100 m from the foot, axial mod 90°) differ by ≥ 10° can discriminate. Each counts for the
reference its direction is closer to. Chance = 5,000 shuffles of foot directions within each distance band. The
test runs six times: the consensus foot, each single definition A–D, and the similarity registration of the parcel
map. Classes: channel centre line and banks, the parcel map's waterway parcels, back boundaries and frontages of
private parcels, temple and shrine property, OSM lanes, walls (DEM steps ≥ 1 m at ≥ 45° outside buildings and the
channel), building long axes. Row offsets measure, every 2 m, how far from the foot private land ends and the
nearest lane, waterway parcel and channel lie. `channel_courses` reads today's channel against the parcel map.

## Choices worth knowing

- The channel (神倉堀端都市下水路) comes from GSI's water areas (optimal vector tiles, ftCode 5000), not OSM, which
  maps only its southern half. Its centre line is the midpoint of each east–west chord.
- The transect follows the pilgrims' route down the mountain (OSM path 121369321 and the steps 121366071) to the
  bridge over the channel, then runs straight to the city hall. Heights are bare ground.
- Labels on the map have independent references in `kansai/qa/points.toml` (`kmk_*`), checked by `run.py`.
