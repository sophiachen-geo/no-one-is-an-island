# Kamikura mountain foot · micro-morphology (last chapter of the Kansai page)

Builds `kansai/data/kamikura.js` (the chapter's map, profile and statistics), `kamikura_relief.jpg` (1 m relief) and
the GIS downloads `kamikura_study.geojson` / `.kml`. Run from a work directory beside the main build's
(`<work>/kmk`, with the main build's `morph/` and `ksj/` one level up):

```bash
T=/path/to/no-one-is-an-island/kansai/tools/kamikura
python3 $T/01_fetch.py     # GSI DEM1A (1 m) tiles for the frame (DEM5A where 1 m is missing) + every OSM feature in it
python3 $T/02_terrain.py   # 1 m grid in JGD2011 / CS VI, slope, the break of slope and the line 25 m upslope of it
python3 $T/03_study.py     # study polygon, transect, statistics, alignment test (→ study.json)
python3 $T/04_export.py /path/to/no-one-is-an-island/kansai   # page data, relief image, GeoJSON/KML
python3 /path/to/no-one-is-an-island/kansai/qa/run.py          # the gate re-checks every number and label
```

## The study area: four rules

| edge  | rule | data |
|-------|------|------|
| west  | 25 m (horizontal) upslope of the break of slope | GSI DEM1A |
| east  | the street bounding the 神倉小学校 compound, continued south on the same line | OSM 121367848 · 1031510641 · 121367953 |
| north | the lane closing the first full block above the school and the temple row | OSM 266991552 · 121369902 |
| south | the street just south of the shrine-entrance cluster, carried west across the foot of the steps | OSM 121367975 · 121370515 · 499568826 |

Break of slope: the edge of ground at least 1 m above the plain (median of near-flat ground) that is steeper than
12° or more than 3 m above the plain, connected to the slopes above 40 m; small spurs removed (opening, r = 2 m).

## Choices worth knowing

- The channel of 市田川 comes from GSI's water areas (optimal vector tiles, ftCode 5000), not OSM: OSM maps only
  its southern half. Its centre line is the midpoint of each east–west chord (exact on straight reaches).
- No surveyed parcels exist here: the Ministry of Justice map (登記所備付地図データ, 2026) for 千穂 and 神倉 is in
  local coordinates (任意座標系), so building footprints stand in for plots.
- The transect follows the pilgrims' route down the mountain (OSM path 121369321 and the steps 121366071) to the
  bridge over 市田川, then runs straight to the city hall. Heights are bare ground (DEM1A has buildings removed).
- Alignment test: each building's direction is the long side of its minimum rotated rectangle. Only buildings
  whose local slope direction differs from the town grid by ≥ 10° can discriminate; each is counted for the
  reference its own grid is closer to. Chance = 5,000 random pairings of the same buildings and slope directions
  within each distance band; one-sided p = share of shuffles at or above the observed share.
- Labels on the map have independent references in `kansai/qa/points.toml` (`kmk_*`), checked by `run.py`.
