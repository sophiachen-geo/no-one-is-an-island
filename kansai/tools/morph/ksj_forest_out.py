import shapely, numpy as np, json, sys, os
from shapely.geometry import Polygon, MultiPolygon, mapping
sys.path.insert(0, os.path.dirname(__file__))
from geoutil import area_km2
D = sys.argv[1]
HOLE_MIN = 0.5   # km2
PART_MIN = 0.1   # km2
TOL = 0.001      # deg
u = shapely.from_wkb(open(f'{D}/raw/ksj/forest_union.wkb', 'rb').read())
stats = json.load(open(f'{D}/raw/ksj/forest_stats.json'))
parts = shapely.get_parts(u)
pa = area_km2(parts)
keep = parts[pa >= PART_MIN]
dropped_parts = int((pa < PART_MIN).sum()); dropped_parts_km2 = float(pa[pa < PART_MIN].sum())
out = []; nh_drop = 0; nh_keep = 0
for p in keep:
    ints = [r for r in p.interiors]
    if ints:
        ha = area_km2(np.array([Polygon(r) for r in ints]))
        kept = [r for r, a in zip(ints, ha) if a >= HOLE_MIN]
        nh_drop += len(ints) - len(kept); nh_keep += len(kept)
    else:
        kept = []
    out.append(Polygon(p.exterior, kept))
mp = MultiPolygon(out)
s = shapely.simplify(mp, TOL, preserve_topology=True)
s = shapely.transform(s, lambda c: np.round(c, 5))
if not s.is_valid:
    print('fixing invalid after rounding:', shapely.is_valid_reason(s))
    s = shapely.make_valid(s)
    s = shapely.union_all([g for g in shapely.get_parts(s) if g.geom_type in ('Polygon', 'MultiPolygon')])
s = shapely.clip_by_rect(s, 135.25, 33.38, 136.42, 34.45)
if s.geom_type == 'Polygon': s = MultiPolygon([s])
print('valid', s.is_valid, s.geom_type, 'parts', shapely.get_num_geometries(s), 'coords', shapely.get_num_coordinates(s))
fa_out = float(area_km2(s))
props = {
  "name": "森林 (forest cover)",
  "source": "国土数値情報 土地利用細分メッシュ L03-b-21 (2021, 100 m mesh), JGD2011",
  "landuse_code": "0500",
  "landuse_label": "森林",
  "mesh_files": ["L03-b-21_5035", "L03-b-21_5036", "L03-b-21_5135", "L03-b-21_5136"],
  "forest_km2_raw": stats["forest_km2"],
  "land_km2": stats["land_km2"],
  "inland_water_km2": stats["inland_water_km2"],
  "forest_share": stats["forest_share"],
  "forest_share_excl_inland_water": stats["forest_share_excl_inland_water"],
  "forest_km2_generalised": round(fa_out, 1),
  "processing": f"dissolved 100 m cells; parts < {PART_MIN} km2 dropped ({dropped_parts} parts, {dropped_parts_km2:.1f} km2); holes < {HOLE_MIN} km2 filled ({nh_drop} holes, kept {nh_keep}); simplified {TOL} deg (preserve topology); coords rounded to 1e-5 deg",
}
fc = {"type": "FeatureCollection",
      "name": "forest",
      "summary": {"forest_share": stats["forest_share"], "forest_km2": stats["forest_km2"], "land_km2": stats["land_km2"],
                  "definition": "forest (L03b_002=0500) area / land area (all cells except 1500 海水域 and cells absent from the dataset = open sea) within the frame 135.25-136.42E, 33.38-34.45N; areas on GRS80 ellipsoid"},
      "features": [{"type": "Feature", "properties": props, "geometry": mapping(s)}]}
json.dump(fc, open(f'{D}/forest.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(props, ensure_ascii=False, indent=1))
print('size', os.path.getsize(f'{D}/forest.geojson'))
