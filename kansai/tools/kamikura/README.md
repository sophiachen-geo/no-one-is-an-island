# Kamikura mountain foot · micro-morphology (last chapter of the Kansai page)

Builds `kansai/data/kamikura.js` (the chapter's map, figures and statistics), the ground layers
`kamikura_{relief,elev,slope,lrm,curv}.jpg` (1 m), and the GIS downloads `kamikura_study.geojson` / `.kml` and
`kamikura_cadastre.geojson`. Run from a work directory beside the main build's (`<work>/kmk`, with the main build's
`morph/` and `ksj/` one level up, and the Ministry of Justice zip for 新宮市 in `moj/`):

```bash
T=/path/to/no-one-is-an-island/kansai/tools/kamikura
python3 $T/01_fetch.py         # GSI DEM1A (1 m) tiles for the frame (DEM5A where 1 m is missing) + every OSM feature in it
python3 $T/02_terrain.py       # 1 m grid in JGD2011 / CS VI, slope, the break of slope and the line 25 m upslope of it
python3 $T/03_study.py         # study polygon, transect, statistics, the school refuge's hazards (→ study.json)
python3 $T/05_terrain_plus.py  # which DEM the ground can bear (coverage, benchmarks, DEM5A), local relief, curvature
python3 $T/06_foot.py          # the mountain foot, four ways, on cross-profiles every 2 m (→ foot.json)
python3 $T/07_parcels.py       # the MoJ parcel map (任意座標系) registered to GSI road edges; spline check (→ parcels.json)
python3 $T/08_align.py         # what follows the foot: nine classes, effects, intervals, q (→ align.json, walls.json, …)
python3 $T/09_export.py /path/to/no-one-is-an-island/kansai   # page data, ground layers, GeoJSON/KML
python3 $T/gazes.py /path/to/no-one-is-an-island/kansai      # only the comparison of gazes, after editing field/gazes.csv
python3 /path/to/no-one-is-an-island/kansai/qa/run.py          # the gate re-checks every number and label
```

`gsi.py` reads GSI's optimal vector tiles (road edges, water edges, buildings, benchmarks); `mojparse.py` reads the
Ministry of Justice 地図XML.
`sacred.py` (called by `09_export.py`) builds the religious flow: the climb and its markers, the vertical section and
the town figure. It fetches two OpenStreetMap extracts from Overpass on first run and keeps them in the work
directory: `osm_streets_hayatama.json` (highways between Kamikura and Hayatama, for the walk) and
`osm_rivers_town.json` (waterways and coastline of the town).

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
  depth. 28% of the area is under buildings, where DEM1A is interpolated (the mask that leaves this ground out of the
  analyses also takes every cell an outline crosses: 31%).
- Local relief = ground minus its Gaussian-smoothed surface (σ 8 m). Profile and plan curvature are computed on ground
  smoothed with σ 2.5 m; negative profile curvature = concave (a foot).
- The foot is found on 310 cross-profiles (every 2 m, perpendicular to the front smoothed over 41 m, 40 m upslope to
  60 m out) as (A) the mask edge, (B) the first point 1 m above the profile's own plain, (C) the most concave point
  between the plain and 10 m above it, (D) the knee of a two-segment fit. The consensus is their median. A and B both
  use a 1 m threshold (A over the whole frame's plain, 6.05 m; B on each profile) and agree most closely.
- Steepness at the foot is the steepest 1 m step in the 7 m window ending 1 m past the foot; the same statistic 9–16 m
  up the face is as steep or steeper (≥ 45° on 66% of profiles against 46%), so it shows the face running steep almost
  to the foot, not a separate cut.

## The parcel map (07)

The sheet 「新宮・千穂一丁目・神倉一丁目他」 is in arbitrary coordinates, digitised from cadastral drawings. Its roads
(道) and waterways (水) are unnumbered parcels of their own; every other parcel is a numbered lot (地番), whoever owns it
(the code's kind "private" means numbered; the page and the download say "numbered"). The fragment holding 千穂一丁目
is placed by matching the school parcel
(715-3) to the school's OSM outline, then by fitting its road parcels to GSI road edges (truncated chamfer distance;
similarity, then affine). The drawing must be enlarged 13–16% (縄伸び) and turned about 14°; road parcels then sit a
median 1.2 m from the road edges. Parcel numbers are not published in the download.

A thin-plate spline (scipy `RBFInterpolator`, degree 1) tests whether the drawing is stretched unevenly. Its pairs are
road-parcel outline points every 5 m and the nearest GSI road edge within 6 m, after the affine fit. The smoothing is
chosen among 1, 10 … 10⁶ by leaving out each north–south third of the fragment in turn: the similarity and affine
fits are refitted on the other two thirds, the spline is trained on their pairs, and all three are scored on the third
left out (`tps.zones`). The stiffest setting wins, so the spline is practically the affine fit; on a third left out
the road parcels lie a median 1.3–2.1 m from the road edges (affine 1.3–1.9 m, similarity 1.5–1.7 m). The page uses
the affine fit; the spline (`rings_tps`) and the similarity fit are the two other registrations in step 8.

## What follows the foot (08)

Each feature is cut into pieces of at most 10 m; a boundary shared by two parcels counts once. Only pieces where the
local foot direction (±10 m) and the town grid (GSI road edges > 100 m from the foot, axial mod 90°) differ by ≥ 10°
can discriminate. Each counts for the reference its direction is closer to (statistic: the length-weighted share
that follows the foot; buildings by footprint area). Chance is a circular shift: the foot's sequence of local
directions is slid along the foot by every offset of at least 50 m (25 profiles) and the share recomputed, so that
neighbouring pieces, which are not independent, move together; `p_100` repeats it with offsets of at least 100 m.
(The first version shuffled single pieces; that treats neighbours as independent and gave p-values far too small for
long lines, and uninformative ones for clustered short edges. It is kept as `p_perm` for the record.) `n_units`
counts the distinct lines behind a result. The effect is the observed share minus the mean shifted share (points),
with a 95% interval from a moving-block bootstrap along the foot (blocks of 25 profiles = 50 m, 4,000 draws). The
primary family is every class in its band next to the foot (0–25 m; steep steps −15–0 m); Benjamini–Hochberg q
controls the false discovery rate over it (`q_primary`, `q_primary_100` with the 100 m offsets) and, for the other
bands, over all 29 class × band tests (`q_all`, `q_all_100`), each from the unrounded p. `bends` says how much of the
front the test can use (the foot ≥ 10° off the grid: 12 bends, 64% of it). The test is rerun with each single foot
definition A–D and with the similarity and spline registrations of the parcel map; those runs are reported as
effects (`sensitivity`), not counted as votes. Classes: channel centre
line and banks, the parcel map's waterway parcels, back boundaries and frontages of numbered parcels, temple and
shrine property, OSM lanes, steep steps (DEM steps ≥ 1 m at ≥ 45° outside buildings and the channel: walls, cut faces
or rock), building long axes. Row offsets measure, every 2 m, how far from the foot the numbered parcels end and the
nearest lane, waterway parcel and channel lie. `channel_courses` reads today's channel against the parcel map:
shares in the unnumbered strips, in numbered parcels and more than 3 m inside them, in the school's parcel.

## Choices worth knowing

- The school refuge (03, `stats.school`): GSI's 指定緊急避難場所 points for Shingū (`sites_30207.csv`, or `$GSI_SITES`)
  are placed in the GSI building outlines that contain them; the gym and the school building are then measured
  against the A33-25 debris-flow zones, the A31b-25 flood meshes (planned and maximum, by depth class) and
  Wakayama's 2026 maximum tsunami (`$TSUNAMI2026`, default `../tsunami2026`, from `tools/tsunami2026`), the same
  layers as the main page. The city's own safety ratings for the two sites come from its list (info/123).
- The channel (神倉堀端都市下水路) comes from GSI's water areas (optimal vector tiles, ftCode 5000), not OSM, which
  maps only its southern half. Its centre line is the midpoint of each east–west chord.
- The transect follows the pilgrims' route down the mountain (OSM path 121369321 and the steps 121366071) to the
  bridge over the channel, then runs straight to the city hall. Heights are bare ground.
- Labels on the map have independent references in `kansai/qa/points.toml` (`kmk_*`), checked by `run.py`.

## The religious flow (sacred.py)

- The climb: DEM1A every 1 m along OSM's steps (way 121366071) and the path to the rock (way 121369321); slope classes
  over 2 m; the steepest 10 m window. Markers: every OSM stele, board, torii or place of worship within 12 m of the
  transect up to the 下馬 stone, plus the four small shrine buildings on the steps.
- The section: the transect from the rock to the foot of the steps, the shortest walk on OSM's streets to 熊野速玉大社
  (trunk roads excluded), then straight to the nearest edge of GSI's water area. Heights from DEM1A inside the frame and
  the main build's DEM5A beyond; none over water. The river to its mouth is measured along OSM's Kumano centre line
  (way 59234786, from MLIT 国土数値情報 W05), whose meeting with OSM's coastline is the mouth.
- The town figure: GSI water areas (5000), 1:25,000 contours every 40 m (7351), roads (27xx; national and prefectural
  roads, others 3 m or wider) and the railway (8201); OSM's 市田川, the Kumano's centre line and the coastline. Places are
  checked against independent coordinates in `kansai/qa/points.toml` (`kmc_*`); the flows join places in order, not
  along routes.
- Sources for the text (shrine, city, prefecture, Agency for Cultural Affairs, Kotobank, UNESCO, the press) are in
  `kansai/qa/register.toml` under “Kamikura · 流れ · sacred”.

## Comparing gazes (gazes.py)

`kansai/field/gazes.csv` codes every image of Kamikura on six publishers' pages (the promotional gaze, maps and
diagrams kept but not counted), the four in Shingū's 2012 master plan, the one plate of the Kubo studio's 1913 album
(NDL, public domain) and our ten photographs at the foot, by the frame of `kansai/field/README.md`: where the camera
stands (mountain, threshold, foot, town), whether the town is in the frame, the breadth of view and up to two of
Gou & Shibata's categories (Channel added). `gazes.py` summarises it into `kamikura.js` → `gaze` (`09_export.py` calls
it too); our photographs' distance from the foot comes from their EXIF positions in `fieldnotes.js` against the foot
line. The QA gate recomputes every label of the figure (`check_gaze`) and every count in the text from that summary.

