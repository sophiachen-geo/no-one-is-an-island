# Shingū story-map geodata (morphology set)

Everything was fetched on **2026-09-30**. All outputs are GeoJSON in lon/lat (EPSG:4326). The KSJ sources use JGD2011/JGD2000, which differ from WGS84 by well under 1 m here, so their coordinates were used unchanged.
Map frame: west 135.25, south 33.38, east 136.42, north 34.45.
All areas were computed in an equal-area projection (Albers on GRS80, `scripts/geoutil.py`) or on the GRS80 ellipsoid.

| File | Content | Features | Size (gzip) |
|---|---|---|---|
| `peaks.geojson` | OSM `natural=peak` nodes that have a name (the frame has no `natural=volcano`) | 333 points (316 with `ele`) | 74 KB (13 KB) |
| `ranges.geojson` | OSM `natural=ridge` / `natural=mountain_range` / `place=region` with a name | 1 line | 1 KB |
| `protected.geojson` | Natural-park and nature-conservation zones from KSJ (a fallback, see below), plus 3 named OSM natural-monument areas | 8 (5 MultiPolygon, 3 Polygon) | 317 KB (89 KB) |
| `forest_names.geojson` | Named OSM `landuse=forest` / `natural=wood` / `leisure=nature_reserve` | 12 (11 polygons, 1 point) | 16 KB |
| `forest.geojson` | Dissolved forest cover from KSJ L03-b-21 (100 m mesh, 2021), code 0500 森林 | 1 MultiPolygon (206 parts) | 221 KB (37 KB) |
| `buildings.geojson` | GSI optimised vector tile building footprints (z16) for central Shingū, Kōyō, Miwasaki and Kihō/Udono | 29,274 polygons | 7.3 MB (0.98 MB) |

The `scripts/` folder holds the processing code and Overpass queries (`q_*.txt`). The `raw/` folder holds the downloaded sources, the z16 tiles, previews (`raw/preview/*.png`) and intermediate files.

---

## peaks.geojson
- **Source:** OpenStreetMap via Overpass `https://maps.mail.ru/osm/tools/overpass/api/interpreter`. The query was `node["natural"="peak"]` and `node["natural"="volcano"]` in the frame bbox (`scripts/q_peaks.txt`), with data as of 2026-09-30T18:35Z.
- **Licence:** ODbL 1.0, "© OpenStreetMap contributors".
- **Processing:** 532 nodes were returned. The 199 unnamed ones were dropped and 333 named peaks were kept. `ele` was parsed to a number in metres, accepting forms like "1915", "1915 m", full-width digits and ft; every value parsed. It is `null` for the 17 peaks without a tag. Properties are `name`, `name:en` (when present), `ele`, `osm_id` and `natural`, plus `name:ja-Hira`, `name:ja-Latn`, `alt_name` and `wikidata` when present. `ele_raw` is added only where the raw tag differed from the parsed value. Features are sorted by `ele` in descending order.

## ranges.geojson
- **Source/licence:** as above (`scripts/q_ranges.txt`).
- **Result:** there is only one feature, **千穂ヶ峯** (Mt. Chihogamine), a `natural=ridge` way/1250325594 in Shingū, 1.29 km long. OSM has **no** `natural=mountain_range` or `place=region` features in the frame, and none named 大峰山脈, 果無山脈, 台高山脈 or 紀伊山地. A broader search for names containing 山脈/山地/連峰/山系/奥駈/大峯/台高/果無 (`q_ranges2.txt`) found only trails, roads and signs. OSM does have 13 named `natural=saddle` passes, such as 三越峠, 岩上峠, 牛廻越, 笠捨越 and 高見峠. These were not added because they were not requested.

## protected.geojson
- **Requested:** the OSM boundary of 吉野熊野国立公園.
- **What OSM has:** nothing usable. The frame has no `boundary=national_park` or `boundary=protected_area` objects at all (`q_prot_tags.txt`). A name search found only way/979504733, a 0.03 km² `leisure=park` in 熊野市 久生屋町 that happens to be named "吉野熊野国立公園", plus information-board nodes. Both were excluded. No ways had to be polygonized.
- **Fallback used:** 国土数値情報 **自然公園地域 A10-15** and **自然保全地域 A11-15** (FY2015) for 三重 (24), 奈良 (29) and 和歌山 (30).
  - Downloaded from `https://nlftp.mlit.go.jp/ksj/gml/data/A10/A10-15/A10-15_{24,29,30}_GML.zip` and `.../A11/A11-15/A11-15_{24,29,30}_GML.zip`. The page is `https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A10-2015.html`.
  - **Licence:** オープンデータ (CC BY 4.0; only 岡山県 is restricted to non-commercial use, which does not apply here). Credit as 「出典：国土数値情報（自然公園地域・自然保全地域データ）（国土交通省）」.
  - **Caveat:** A10 does **not** record park names. OBJ_NAME is empty in both the 2011 and 2015 editions. The zones therefore cover *all* natural parks together: 吉野熊野国立公園, 高野龍神国定公園, 金剛生駒紀泉国定公園 and the prefectural parks. They cannot be split by park from this source. The Ministry of the Environment boundary services (gis.biodic.go.jp, www2.env.go.jp EADAS) were blocked by the network proxy.
  - **Processing:** each zone class was selected, clipped to the frame, dissolved, simplified to 0.0005° (about 50 m, topology preserved) and rounded to 1e-5°. Parts smaller than 0.002 km² were dropped; the count is in each feature's properties.
  - **Features:** `zone_code` 11 自然公園地域 (1,986 km² in frame), 12 特別地域 (599 km²), 13 特別保護地区 (44 km²), 14 自然保全地域 (6.8 km²) and 16 自然保全地域 特別地区 (6.4 km²). There is no 15 原生自然環境保全地域 in the frame. `municipalities_listed` repeats the source CTV_NAME values, which are often blank.
- **OSM named natural-monument-type areas** (`layer: osm_named_nature_area`, ODbL): 九木神社樹叢 (relation/15919589, `natural=wood`, description 国指定天然記念物, 0.046 km²), 浮島の森 (way/211578007, `landuse=forest`, 0.0037 km²) and 御船島 (way/212510589, `natural=wood`, heritage=1, 0.0027 km²). OSM has no area for 那智原始林 or 大杉谷. The relevant items exist only as points and were left out because areas were requested: node/7467439385 `natural=wood` "Nachi Primeval Forest" (name:en only) at 33.6762,135.8919; node/3035471584 神島 `historic=natural_monument` at 33.7031,135.3756; node/4170974856 妹山 `leisure=nature_reserve` at 34.3940,135.8705.

## forest_names.geojson
- **Source/licence:** OSM/ODbL (`scripts/q_forest.txt`).
- **Processing:** relation multipolygons were assembled from member ways with shapely polygonize (outer minus inner). Properties are `name`, a subset of tags, `osm_id` and `area_km2`. The node named "knn" (`natural=wood`) was dropped as junk. Features are not clipped: 瀧原宮 and 長野公園 extend slightly past the frame edge.
- **Features by area (km²):** 瀧原宮 0.458, 長野公園 0.072, 鳥の巣平和公園 0.050, 九木神社樹叢 0.046, おやま 0.019, 八上神社の森 0.011, こやま 0.005, 浮島の森 0.0037, 昼嶋 0.0028, 御船島 0.0027, スギ 0.0025, and 妹山 as a nature-reserve point. OSM has only these 12.

## forest.geojson
- **Source:** 国土数値情報 土地利用細分メッシュ **L03-b-21** (2021 / 令和3年度, 100 m mesh, JGD2011). This is the newest edition; the page says 「最新のデータはデータ基準年度 2021年度（令和3年度）版です」. The page is `https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L03-b-2021.html`. The files are `https://nlftp.mlit.go.jp/ksj/gml/data/L03-b/L03-b-21/L03-b-21_{5035,5036,5135,5136}-jgd2011_GML.zip`, and the shapefiles inside were used.
- **Licence:** オープンデータ (CC BY 4.0), 国土数値情報ダウンロードサイトコンテンツ利用規約（政府標準利用規約準拠版）. Credit as 「出典：国土数値情報（土地利用細分メッシュデータ）（国土交通省）」.
- **Code:** attribute `L03b_002`. The code list LandUseCd-09 (`https://nlftp.mlit.go.jp/ksj/gml/codelist/LandUseCd-09.html`) confirms **0500 = 森林** 「多年生植物の密生している地域」 for the 2009, 2014, 2016 and 2021 editions.
- **Processing:**
  1. The 1.62 M mesh records were read. Each 10-digit mesh code was decoded to an exact grid cell of 1/800° × 1/1200°, and the cell position was checked against the shapefile geometry.
  2. A 1284 × 936 grid was built for the frame. The grid edges coincide exactly with the frame.
  3. Horizontal runs of forest cells were combined with union_all into one exact MultiPolygon: 2,731 parts and 8,932 holes.
  4. Parts under 0.1 km² were dropped (2,525 parts, 54.4 km², 0.7 % of forest). Holes under 0.5 km² were filled (8,809 filled, 122 kept).
  5. The result was simplified at 0.001° with topology preserved, rounded to 1e-5° and clipped to the frame.
- **Forest share:** `forest_share` = forest ÷ land = 7,434.1 / 8,656.0 km² = **0.8588**, stored in the feature properties and in the FeatureCollection `summary`. Land is every cell in the frame except 1500 海水域 and cells absent from the dataset (all open sea). Excluding 1100 河川地及び湖沼 from land as well gives 0.8767. Cell areas were computed on the GRS80 ellipsoid. After generalisation the polygon area is 7,696.9 km², because filled holes add area and dropped parts remove it.

## buildings.geojson
- **Source:** GSI 最適化ベクトルタイル (experimental_bvmap) at `https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{z}/{x}/{y}.pbf`. The feature-code list is at `https://maps.gsi.go.jp/help/pdf/vector/optbv_featurecodes.pdf`.
- **Licence/attribution:** 国土地理院コンテンツ利用規約 / 地理院タイル. Attribution is required: **「出典：国土地理院」** (or 「地理院タイル」) with a link to `https://maps.gsi.go.jp/development/ichiran.html`. GSI's own style for this tileset credits 「国土地理院最適化ベクトルタイル」.
  - Caveat: the building data derive from 電子国土基本図, which is a 基本測量成果. GSI's tile page notes that re-using basic survey results *may* require an application under 測量法 when the data are not simply loaded as tiles in real time. Check 「国土地理院の地図の利用手続」 before publishing this file itself.
- **Layer and zoom:** the tiles contain the layers road, river, contour, symbol, elevation, label, landformp/landforml/landforma, boundary, **building**, waterarea, structurel/structurea, railway, coastline, transp and searoute. Buildings are in layer **`building`** at z13–z16. The code list shows ZL14–17, with ZL17 stored in the ZL16 tiles; z17 returns 404. **z16** is the most detailed level and was used: extent 4096, buffer 80, about 0.12 m per unit.
- **Attribute schema** of `building` at z16:
  - `ftCode` (int): 3101 普通建物, 3102 堅ろう建物, 3103 高層建物, 3111 普通無壁舎, 3112 堅ろう無壁舎.
  - `orgGILvl` (string, source map level, e.g. "2500").
  - `lvOrder` (int, drawing level).
  - Features have no IDs (all 0). Every footprint appears twice: once as a Polygon (the fill) and once as a LineString/MultiLineString (the outline stroke).
- **Area:** lon 135.955–136.020, lat 33.655–33.760, which is z16 tiles x 57517–57529 and y 26232–26255. 312 tiles were requested: 303 returned 200, 9 open-sea tiles returned 404, and 164 tiles contain buildings.
- **Processing:**
  1. Only Polygon fills were kept (35,608 outline lines were skipped).
  2. Each polygon was clipped to its own tile square (dropping the buffer duplicates) and moved to global z16 pixel coordinates.
  3. Pieces from neighbouring tiles that share more than 0.5 units of edge on the common tile border were joined with union-find (1,207 links) and merged with snap + union. All results are single valid Polygons, with no leftover duplicates (0 pairs overlap by more than 50 %).
  4. Collinear cut vertices were removed. Coordinates were converted from Web Mercator to lon/lat and rounded to 1e-6° (about 0.1 m).
  5. A building is kept when its representative point lies in the area.
- **Result:** 29,274 buildings: 3101 = 26,676, 3102 = 529, 3111 = 2,066, 3112 = 3. Properties are `ftCode`, plus `lvOrder` / `orgGILvl` only when they differ from the defaults (0, "2500"). The label mapping is stored in the FeatureCollection member `ftCode_labels`.

## What failed or is missing
- There is no OSM boundary for 吉野熊野国立公園; the KSJ A10 fallback does not carry park names.
- OSM has no mountain-range or region features in the frame.
- These peaks from the requested list are missing from OSM as peaks: 大台ヶ原 (only 日出ケ岳 1695.1), 妙法山 (only the temple 妙法山阿弥陀寺), 大雲取山 (only the route 大雲取越), 神倉山 (only 神倉神社), 果無山, and 烏帽子山 at 909 m (only 大烏帽子山 362.4).
- The Overpass mirror often returned 504 「server too busy」; `scripts/ovq.sh` retries with backoff.
