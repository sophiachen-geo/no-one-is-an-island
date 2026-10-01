# Paused 2026-10-01 ~09:15 UTC — resume notes (work in progress, not for main)

This folder is a save point only. Do not merge it: before opening the next PR, rebuild the branch from
`origin/main` and bring over only the code commits (the tarballs must not enter main's history).

## Restore
```bash
S=/tmp/claude-0/-home-user-no-one-is-an-island/12597f4f-a471-563e-939e-90ea1b9703e1/scratchpad   # or any scratch dir
mkdir -p $S/research $S/bike && tar xzf wip/research_2026-10-01.tar.gz -C $S/research
tar xzf wip/bike_work_2026-10-01.tar.gz -C $S/bike && cp kansai/tools/bike/*.py $S/bike/
tar xzf wip/scratch_misc_2026-10-01.tar.gz -C $S          # verify_live.mjs, crit/main_text.txt, pr/*.md
pip install pillow-heif gpxpy fitdecode mapbox-vector-tile   # photo + GSI tile readers
```
If the container was recycled, the main build work dir (`$S/geo`: KSJ zips, OSM, DEM5A mosaic) must be rebuilt
with `kansai/tools/README.md` (01_fetch.sh …). The bike DEM cache (`bike/dem_tiles`, `bike/bvmap`) refills on demand.

## User requests still open (latest first)
1. "save everything … stop … resume in 2 h 50 min" — this save point; resume scheduled with send_later.
2. "Yes continue and never stop until all is done"; "make absolutely sure there's no mistakes";
   "always … the most recent and the most precise data you can get for free".
3. Photos: Drive folder "Shingu field photos (drop here)" id `1U8tOcUww1Ri35EG1H1BNTUUVefyuUw6u`
   (https://drive.google.com/drive/folders/1U8tOcUww1Ri35EG1H1BNTUUVefyuUw6u) — EMPTY at 09:10. Check it first.
   Ingest with `kansai/tools/photos/ingest.py` (EXIF GPS/time, metadata-free web copies). Look at every photo
   before publishing (privacy: faces, plates, home). They also feed task #29 (Gou & Shibata "compare gazes").
4. "we went to the three main shrines by bike so you need to do a full mapping of all bike routes" (#36).
5. The critique ("Try implementing these ?"): priorities 1 reframe around concentrate vs evacuate;
   2 tsunami evacuation per building and person; 3 frequency-tiered, depth-classed, age-weighted exposure on
   both banks; 4 network criticality under hazards; 5 split and re-headline Kamikura (+ effect sizes with
   intervals, FDR, pre-specified classes, bend length; affine vs TPS registration with residuals by zone).
   Also: form fixes (duplicated boards, "three waters" vs "four pathways", evaluative adjectives, numeric
   opening, "field notes" without fieldwork), Iseji KML rights → OSM, replace the 2016 tsunami layer,
   路地 in text only (never map Dōwa districts).

## Bike routes — state (code in kansai/tools/bike/, outputs in bike_work tarball)
- Network: OSM highways in 33.60–33.90 N × 135.70–136.06 E, 9 tiles from maps.mail.ru Overpass,
  osm_base 2026-10-01T08:35–08:42Z (mirror checked fresh; overpass-api.de reset/504; private.coffee and
  kumi were stale — cycle.json came from private.coffee with base 2026-05-31: REFETCH from mail.ru).
- Legality (route.py): no motorway/motorway_link (那智勝浦新宮道路, 新宮紀宝道路 are motorway in OSM),
  no motorroad, no bicycle=no, foot-only ways excluded unless bicycle=yes.
- Alternatives: plateau method (plateau.py, S = 1.6) → union → 46 chains, 32 junctions (corridors.py) →
  presentation graph 26 nodes / 37 corridors (present.py; short chains < 400 m contracted, dual
  carriageways merged). Shortest legal rides: Hongū→Hayatama 33.6 km (NR168, ≈170 m up);
  Hayatama→Nachi 21.5 km (NR42 + 県道46, ≈160 m); Nachi→Hongū 52.7 km via Shingū (≈330 m).
  Alternatives: Mie left bank 県道740 (37.3 km), hill roads c7/c38, Mie loop NR311 (50.5 km),
  県道229/45 over 高瀬峠 (c31: 8,974 m surface=ground in OSM, a 41 % stretch at 135.7755,33.765–33.770 —
  flag as unpaved/unverified, not a road-bike route), 県道43/44 inland (c14, c15), unnamed mountain road
  那智山→田長 c3 (max 898 m; surface/access unknown in OSM — check GSI width class).
- Heights: GSI DEM5A (5A>5B>5C>10B) on the OSM line every 20 m; tunnels/bridges interpolated;
  road-bed Viterbi tracking (benchdp.py) removes lateral-misfit noise. Validation: 35 GSI levelling
  benchmarks / spot heights within 15 m: median error ≈0.2–1.3 m. Climb with 5 m hysteresis; range
  (road bed, 10 m) .. (line, 2 m). Remaining artefacts: c31 (unpaved section), c12 gmax 28 % (check).
- Hazards per corridor (hazards.py, corridors.json "haz"): A33 2025 landslide zones (A33_002 2/4 red),
  A31a max flood (national section only), A40-16 tsunami (old H25 — swap for digitised R8 when done).
- Rain closures (Wakayama 異常気象時通行規制, research/bike/wakayama_ijoukisho_kisei.geojson, start/end
  points): NR168 宮井–田辺市境 240 mm; 相賀–田長 320 mm; 本宮–大居 550 mm; 県道46 市野々 460 mm;
  県道43 南平野–小阪 560 mm. Current works: wakayama_doro_kisei_current.geojson. Mie's list: not yet found.
- Official routes (research/bike/, agent stopped before its report): MLIT Pacific Coast Cycle Route KML
  (pcr_mlit_Route_wakayama.kml, _mie.kml), _mymaps/ (w800_pcr.kml, kkr_*.kml, mie_course04/05.kml,
  kumano_area_rental.kml), WAKAYAMA800 facilities (w800_facilities_all.geojson), PDFs (not saved, >1 MB:
  cycling_map_omote_20251112.pdf, cycling_map_ura_20260427.pdf, kumano_de_rentalcycle.pdf,
  190719_taichishinguu.pdf, bwrm_waka_s1/s2.pdf) — re-find URLs in the agent's scripts/logs if needed.
- Next: names (OSM name:ja-Hira readings, e.g. 皆瀬川 Minasegawa, 田長 Tanago, 日足 Hitari, 椋井 Mukunoi),
  GSI width class conflation, export.py → kansai/data/bike.js, chapter "Field notes · three shrines by
  bicycle" (map with chips: routes / climb / rain closures / hazards / official / our ride; route-option
  table; linked profiles with stated VE), register.toml + points.toml entries, QA gate, PR, merge, deploy,
  verify live. Add the user's ride when photos/GPX arrive.

## Critique research (agents' notes in research tarball)
- people.md (complete): 2020 census small areas + 250 m mesh ages both banks (2025 small-area not yet out);
  IPSS 2023: Shingū 2050 15,423 (65+ 50.1 %), Kihō 5,713; vacancy 2023 23.8 % (Kihō not tabulated);
  KSJ P04/P14/P29/P05 subsets; MHLW 2026 facility lists; 立地適正化計画 (2017, rev. Sept 2021) has NO
  防災指針; excludes landslide zones and 津波避難困難地域 but keeps tsunami/flood areas with no depth
  threshold; plan's own 68.2 % of residents in hazard-concern areas (2010 base).
- tsunami.md (complete): no GIS of Wakayama R8 (2026-03-25, PDF raster maps, 7 classes 0.01/0.3/0.5/1/3/5/
  10/20 m) nor Mie 2026 (sheets 21–22, Kihō) — digitise the PDFs (licence allows, credit + 改変);
  R8 Shingū max 13 m, +1 m at 5 min measured ~30 m OFFSHORE (fix the page wording); official difficult-area
  rule: depart 5 min, 0.5 m/s on roads ≥ 3 m, 21 m/min straight line elsewhere, stairs 0.21 m/s, deadline
  1 cm arrival, target < 30 cm or designated building; difficult areas 王子・熊野地 (185 people, unresolved
  FY2024) and 三輪崎 (600, resolved); GSI 指定緊急避難場所 2025-01-23 (Shingū 48 tsunami sites, Kihō 30);
  suggested margin formula in §6. CAO 2025 10 m arrival-time mesh needs a G空間 login — not downloaded.
- flood (agent stopped, no flood.md): see research/flood/ analysis/, tools/ (exposure.py, exposure_results.json,
  houshin_* text of 新宮川水系河川整備基本方針 R3.10, dams_* 協議会 texts, kawaramachi/ sources, clipped
  A31a L2 duration + 家屋倒壊等氾濫想定区域 for Shingū/Kihō). PDFs (kinan_tadankai 多段階 maps) not saved.

## Order of work after resuming
1. Drive folder → photos (if any) → ingest. 2. Finish bike chapter (#36) → PR → merge → deploy → verify live.
3. Critique analyses (#38/#39): digitise R8 tsunami; per-building margin (depart 5/15 min; 0.5/1.0 m/s);
   tiered + depth-classed + age-weighted exposure both banks; network criticality (hazard links removed,
   2011 reopening dates); 4×4 interaction matrix; shrinkage. 4. Text/form rework (#40). 5. Kamikura split +
   statistics (#41). 6. Compare gazes (#29) with the user's photos. Each phase: PR → CI → merge → deploy →
   verify live (scratchpad verify_live.mjs).
