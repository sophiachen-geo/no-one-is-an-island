# The 2026 tsunami assumptions for Shingū and Kihō, digitised

Wakayama (令和8年3月) and Mie (2026年3月, corrected June) replaced their tsunami inundation assumptions in spring 2026 and
published them as PDF maps only: no GIS release exists (checked 2026-10-01; MLIT's 国土数値情報 A40 still holds Wakayama's
2013 and Mie's 2015 assumptions). This folder turns the maps of Shingū (Wakayama, both classes) and Kihō (Mie sheet 22,
maximum class; Mie published no map of the frequent class) into 1 m depth-class grids and polygons, and reads the time the
water reaches every place from Wakayama's 2D animation of the same simulation.

```bash
mkdir work && cd work
bash /path/to/kansai/tools/tsunami2026/run.sh /path/to/main-build/ksj-dir   # needs N03-20260101_30/24.geojson, prefs.geojson
```

| step | what it does |
|---|---|
| `fetch.sh` | the four PDF sheets and two MP4 animations (hashes printed) |
| `raster.py` | reassembles each sheet's map from its embedded JPEG strips, at their own resolution (nothing resampled) |
| `init.py` + `gcps.json` | first placement from facility symbols the maps print (city hall, fire, police, prefectural office; Kihō: town hall, police, fire branch, Udono station) |
| `register.py` | affine fit of the map's grey line work to GSI building outlines (電子国土基本情報, optimal_bvmap-v1 z16, `fetch_obv.py`), robust capped distance; Mie: buildings in Mie only (the sheet draws only Mie's land) |
| `poly.py` | quadratic refinement of the Wakayama fits; residuals by ninths of the sheet |
| `classify.py` | nearest legend colour (fills read from the PDF's vector legend), gaps under line work filled from neighbours; 1 m grid in EPSG:6674 |
| `merge.py` | the two Wakayama sheets of each class on one grid; areas inside Shingū (N03, 2026) |
| `vectorize.py` | polygons per depth class, clipped to the town the map is made for → `tsunami2026/*.geojson` for `07_build.py` |
| `vid_decode.py` | first frame each pixel of the animation is drawn wet (3 frames running; 1 frame = 10 s) and the water level drawn |
| `vid_register.py`, `vid_shift.py` | the animation's map panel placed on GSI aerial photographs (`fetch_photo.py`; used only to find the transform), then the half-pixel shift that best overlays its wet area on the digitised map |

## Checks

- **Areas.** Shingū, maximum class: 289.8 ha digitised, 290 ha in Wakayama's table (report p. 12); frequent class 98.6 ha
  against 100 ha. Kihō: 174.8 ha against Mie's 198 ha; the difference lies under the map's road and railway symbols next to
  the water (about 20 ha, which the classifier cannot see) and on the beach seaward of the N03 coastline (about 5 ha).
- **Registration.** Wakayama sheets: median 0.3–0.4 px (0.4–0.5 m) from GSI building outlines after refinement, the same
  in every ninth of the sheet. Mie sheet 22: median 0.13 px (0.5 m).
- **Animation.** Its wet area inside Shingū overlaps the digitised map with an intersection over union of 0.84; edges agree
  within one panel pixel (9.4 m); the remaining differences are river channels, which the map leaves blank. On the Kihō
  bank, 98 % of Mie's mapped inundation is drawn wet in Wakayama's animation.

## Limits worth knowing

- The polygons are a reading of printed colour classes, not the prefectures' data. Use them until GIS is released.
- R8 treats road and railway embankments as terrain that does not fail (report p. 3). The late wetting of Shingū's inner
  lowland in the animation (about half an hour) depends on that.
- The animation shows one case of the simulation; the map is the envelope of four (Wakayama's cases 2, 3, 8, 10). Its
  frame covers central Shingū and the Udono bank of Kihō, not Miwasaki, Sano or Kihō north of Udono.
- Wakayama's maps and animations: 和歌山県ホームページ公開情報利用規約 (CC BY 4.0-compatible; 改変: digitised).
  Mie's: CC BY 4.0. The GSI base map printed under them is not used or reproduced; GSI photographs and vector tiles serve
  only to compute transforms.
