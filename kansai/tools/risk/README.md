# Exposure, evacuation and the road network — Shingū and Kihō

Builds `kansai/data/risk.js`: every figure the page quotes about residents by hazard tier, tsunami evacuation margins,
the location plan's zones and road access under hazard, plus what the map draws for them (buildings coloured by their
margin, the designated refuges, the medical centre's warning zone, the single road links). The QA gate reads the numbers
back from that file: prose claims through `rk` checks in `kansai/qa/register.toml`, table cells through their `data-rk`
attribute.

```bash
mkdir rk && cd rk
export KANSAI_GEO=/path/to/main-build-work TSUNAMI_WORK=/path/to/tsunami2026-work OSM_ROADS=/path/to/bike-work/roads.json
bash /path/to/kansai/tools/risk/run.sh /path/to/kansai
```

Inputs (`cfg.py`): the main build's work directory (`ksj/` with N03, A31b-25, A33-25, A55, P04; the GSI DEM5A mosaic),
`tools/tsunami2026`'s work directory (the 1 m depth-class grids and the animation's arrival field) and the OpenStreetMap road
extract of `tools/bike/fetch_tiles.py`. Everything else is downloaded by `fetch.py` (fetched for the page on 2026-10-01).

| step | what it does |
|---|---|
| `fetch.py` | 2020 census (e-Stat: 250 m mesh T001142, small areas T001082 and their boundaries), GSI 指定緊急避難場所 (Shingū and Kihō, updated 2025-01-23), Shingū's 津波一時避難施設・場所 page (2017-02-03), 国土数値情報 P04 (2020), IPSS 2023 projections, OSM sites that are not homes |
| `census.py` | small areas and 250 m cells with total, 65+, 75+; suppressed figures (秘匿) merged into the area or cell that receives them, as e-Stat does |
| `fetch_bld.py` | GSI optimal vector tiles (z16 BldA building outlines, RdCL road centre lines) over every inhabited cell → `obv16/` |
| `citylist.py` | Shingū's 2017 list of temporary tsunami refuges, with the height above sea level of the floor or ground people are sent to |
| `pop_bld.py` | residents per building: weights by footprint (15–2,500 m²; none for sheds or buildings on OSM sites that are not homes), iterative proportional fitting so every cell and every small area keeps its census totals (all ages, 65+, 75+) |
| `sites.py` | the designated tsunami sites with their floor heights (all 43 Shingū buildings on the city's list matched) and the 2026 depth at each |
| `walknet.py` | walking network: GSI road centre lines (every public road, lanes under 3 m included) plus OSM footpaths and steps, tied within 8 m; ground heights from DEM5A |
| `evac.py` | per inhabited building in the 2026 maximum inundation: arrival − departure − walk − climb, four speed models × two refuge sets × three departures; named places (station, city hall, shrine) |
| `expo.py` | residents by tier on both banks: tsunami frequent / maximum class by depth, river flood planned / maximum by depth and duration, house-collapse zones, landslide zones |
| `cve.py` | the 立地適正化計画 zones (A55) against the tiers, by area (2 m grid) and by residents, with the margins |
| `crit.py` | drivable OSM network under hazard scenarios: residents cut off from the three emergency hospitals (P04 救急告示), single links (graph bridges) on main roads, the 2011 closure of Route 168 replayed, how the medical centre is reached |
| `shrink.py` | the margins with the 2050 population (IPSS 2023, under and over 75 scaled separately) |
| `export.py` | → `kansai/data/risk.js` |

## Models and parameters

- **Arrival** — the first frame (frames 10 s apart) in which Wakayama's 2026 animation of the maximum class draws the
  building's ground wet (≈ 1 cm), registered to GSI photographs (`tools/tsunami2026`). The animation's frame covers central
  Shingū and the Udono side of Kihō; for Miwasaki, Sano and Kihō north of its frame the page gives bounds for arrivals at
  6 and 10 minutes (Shingū's own range for Miwasaki; Mie gives 6 minutes to +1 m at 井田).
- **Departure** — 5 minutes (Wakayama's rule, the Cabinet Office's daytime case), 10 (the Cabinet Office at night), 15
  (people who first attend to something).
- **Walking speed** — W: Wakayama's 30 m/min on roads and 21 m/min straight to the network (0.5 / 0.35 m/s); C: the
  Cabinet Office's 2025 speeds for all walkers, 0.70 m/s below a 5 % grade and 0.44 m/s at or above; E: the same for
  people walking with someone who needs help, 0.53 / 0.33 m/s; F: the FDMA's 1.0 m/s. Steps take at least rise / 0.21 m/s.
- **Refuges** — D: the designated tsunami sites; DH: D plus any network vertex on ground at or above the maximum tsunami
  height (Shingū 13 m, Kihō 11 m) outside the inundation. The climb at a site is to the floor the city lists or, where
  none is listed, above the 2026 depth class, at 0.21 m/s.
- **Timing sensitivity** — the 2026 model keeps road and rail embankments standing, and the animation wets central Shingū
  late (median 33 minutes). Capping the arrival at 15 minutes, the upper end Shingū still plans with for 王子・熊野地,
  shows what earlier water means.
- **Road closures** — a link closes where any point on it (every 10 m) lies in the scenario's hazard: tsunami 0.3 m or
  deeper, flood 0.5 m or deeper, a landslide red zone (or any warning zone); bridges and tunnels stay open. Residents
  whose own building is in the hazard are counted apart, not as cut off.

## Checks

- Residents: the fitted buildings add up to the census in every cell and small area; the towns' buildings hold 27,161
  (Shingū) and 10,307 (Kihō) residents against 27,171 and 10,321 in the census.
- Walking network: in three test areas OpenStreetMap alone missed 13–34 % of GSI's road length, hence GSI as the base.
- The city's difficult areas (新宮市津波防災地域づくり推進計画, 2025): 王子・熊野地 185 residents with water at 7–15
  minutes; the model gives 41 short with the 2026 arrival and 837 with water by 15 minutes.

## Limits worth knowing

- Building-level residents are an allocation; sums over areas hold, single buildings may not.
- Walks go to the refuge reached first in time and ignore debris, blocked lanes, crowding and fences.
- Kihō's extent is Mie's map; its arrival is Wakayama's simulation of the same water.
- The road scenarios bound access; shallow water is often passable and dry roads can be blocked.
- Licences: e-Stat (government standard terms, attribution), GSI (公共データ利用規約 1.0), 国土数値情報 (P04, P05, P29
  open; P14 for Wakayama and the 2012 P17/P18 carry a non-commercial condition), IPSS (attribution), OpenStreetMap (ODbL).
