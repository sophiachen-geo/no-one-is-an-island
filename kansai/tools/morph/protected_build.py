import shapefile, glob, json, sys, os, shapely, numpy as np
from shapely.geometry import shape, box, mapping, MultiPolygon, Polygon
sys.path.insert(0, os.path.dirname(__file__))
from geoutil import area_km2
D = sys.argv[1]
FRAME = box(135.25, 33.38, 136.42, 34.45)
TOL = 0.0005
MINPART = 0.002  # km2; parts below ~45x45 m (under the 50 m simplification) dropped
CLASSES = {  # layer suffix -> (dataset, zone label, en)
  '11': ('A10-15', '自然公園地域', 'natural park area (national + quasi-national + prefectural parks; park names not recorded in source)'),
  '12': ('A10-15', '自然公園 特別地域', 'natural park special zone'),
  '13': ('A10-15', '自然公園 特別保護地区', 'natural park special protection zone'),
  '14': ('A11-15', '自然保全地域', 'nature conservation area'),
  '15': ('A11-15', '原生自然環境保全地域', 'wilderness area'),
  '16': ('A11-15', '自然保全地域 特別地区', 'nature conservation area special zone'),
}
def polys(g):
    out = []
    for q in shapely.get_parts(g):
        if q.geom_type == 'Polygon':
            if q.area > 0: out.append(q)
        elif q.geom_type in ('MultiPolygon', 'GeometryCollection'):
            out += polys(q)
    return out
feats = []
for lay, (ds, ja, en) in CLASSES.items():
    geoms = []; munis = set(); n = 0
    for pref in ['24', '29', '30']:
        fs = glob.glob(f'{D}/raw/ksj_parks/a001{pref}00201602{lay}.shp')
        if not fs: continue
        r = shapefile.Reader(fs[0], encoding='cp932')
        for sr in r.iterShapeRecords():
            if not sr.shape.points: continue
            g = shape(sr.shape.__geo_interface__)
            if not g.is_valid: g = shapely.make_valid(g)
            if not g.intersects(FRAME): continue
            geoms.append(g.intersection(FRAME)); n += 1
            cn = sr.record.as_dict().get('CTV_NAME') or ''
            for m in cn.replace('　', ' ').split(): munis.add(m)
    if not geoms:
        print(lay, 'none in frame'); continue
    u = shapely.union_all(geoms)
    u = shapely.make_valid(u)
    u = shapely.union_all(polys(u))
    a_raw = float(area_km2(u))
    s = shapely.simplify(u, TOL, preserve_topology=True)
    s = shapely.transform(s, lambda c: np.round(c, 5))
    if not s.is_valid: s = shapely.make_valid(s)
    s = shapely.union_all(polys(s))
    parts = polys(s); pa = area_km2(np.array(parts))
    n_small = int((pa < MINPART).sum())
    s = MultiPolygon([q for q, a in zip(parts, pa) if a >= MINPART])
    props = {'name': ja, 'name:en': en, 'layer': f'ksj_{ds}', 'zone_code': int(lay), 'source': f'国土数値情報 {"自然公園地域" if ds=="A10-15" else "自然保全地域"} {ds} (2015; prefectures 24 三重, 29 奈良, 30 和歌山), CC BY 4.0',
             'n_source_polygons': n, 'area_km2': round(a_raw, 1), 'dropped_parts_lt_0.002km2': n_small, 'municipalities_listed': sorted(munis)}
    feats.append({'type': 'Feature', 'properties': props, 'geometry': mapping(s)})
    print(lay, ja, 'n', n, 'area', round(a_raw, 1), 'dropped small', n_small, 'parts', shapely.get_num_geometries(s), 'coords', shapely.get_num_coordinates(s))
osm = json.load(open(f'{D}/raw/prot_osm_features.json'))
for f in osm:
    print('osm', f['properties'].get('name'), f['properties'].get('area_km2'))
feats += osm
fc = {'type': 'FeatureCollection', 'name': 'protected',
      'note': 'OSM has no boundary=national_park/protected_area for 吉野熊野国立公園 (checked 2026-09-30); KSJ A10-15 natural-park zones (all park types, unnamed in source) are supplied as fallback. OSM named natural-monument-type areas appended.',
      'features': feats}
json.dump(fc, open(f'{D}/protected.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))
print('size', os.path.getsize(f'{D}/protected.geojson'))
