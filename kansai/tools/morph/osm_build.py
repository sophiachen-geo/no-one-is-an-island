import json, sys, os, shapely, numpy as np
from shapely.geometry import Polygon, LineString, Point, mapping, box, MultiPolygon
sys.path.insert(0, os.path.dirname(__file__))
from geoutil import area_km2, to_m
D = sys.argv[1]
FRAME = box(135.25, 33.38, 136.42, 34.45)
def rnd(g, nd=6): return shapely.transform(g, lambda c: np.round(c, nd))
def way_geom(e):
    c = [(p['lon'], p['lat']) for p in e['geometry']]
    if len(c) >= 4 and c[0] == c[-1]: return Polygon(c)
    return LineString(c)
def _poly_from_lines(lines):
    merged = shapely.line_merge(shapely.union_all(lines))
    parts = list(shapely.get_parts(merged))
    return shapely.union_all(list(shapely.get_parts(shapely.polygonize(parts))))
def rel_geom(e):
    outers = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in e['members'] if m['type'] == 'way' and m['role'] in ('outer', '') and m.get('geometry')]
    inners = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in e['members'] if m['type'] == 'way' and m['role'] == 'inner' and m.get('geometry')]
    o = _poly_from_lines(outers)
    if inners:
        o = o.difference(_poly_from_lines(inners))
    return o
TAGKEEP = ('name', 'name:en', 'name:ja', 'name:ja-Hira', 'name:ja-Latn', 'landuse', 'natural', 'leisure', 'boundary', 'protect_class', 'heritage', 'heritage:operator', 'ref:whc', 'description', 'designation', 'wikidata', 'wikipedia', 'source', 'note', 'religion')
def props(e, extra=None):
    t = e.get('tags', {})
    p = {k: t[k] for k in TAGKEEP if k in t}
    p['osm_id'] = f"{e['type']}/{e['id']}"
    if extra: p.update(extra)
    return p
# ---------------- ranges
js = json.load(open(f'{D}/raw/osm_ranges.json'))
feats = []
for e in js['elements']:
    g = way_geom(e) if e['type'] == 'way' else (Point(e['lon'], e['lat']) if e['type'] == 'node' else rel_geom(e))
    L = float(shapely.length(to_m(g))) / 1000 if g.geom_type in ('LineString', 'MultiLineString') else None
    feats.append({'type': 'Feature', 'properties': props(e, {'length_km': round(L, 2) if L else None}), 'geometry': mapping(rnd(g))})
json.dump({'type': 'FeatureCollection', 'name': 'ranges', 'features': feats}, open(f'{D}/ranges.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))
print('ranges', [(f['properties'].get('name'), f['properties'].get('natural'), f['geometry']['type'], f['properties']['length_km']) for f in feats])
# ---------------- forest names
js = json.load(open(f'{D}/raw/osm_forest.json'))
relg = {e['id']: e for e in json.load(open(f'{D}/raw/osm_rel_15919589.json'))['elements']}
nodexy = {e['id']: (e['lon'], e['lat']) for e in json.load(open(f'{D}/raw/osm_nodes_pts.json'))['elements']}
feats = []; skipped = []
for e in js['elements']:
    t = e.get('tags', {})
    if t.get('name', '').strip().lower() in ('knn',):
        skipped.append((e['type'], e['id'], t.get('name'))); continue
    if e['type'] == 'way': g = way_geom(e)
    elif e['type'] == 'relation': g = rel_geom(relg[e['id']])
    else: g = Point(*nodexy[e['id']])
    if not g.is_valid: g = shapely.make_valid(g)
    a = float(area_km2(g)) if g.geom_type in ('Polygon', 'MultiPolygon') else None
    feats.append({'type': 'Feature', 'properties': props(e, {'area_km2': round(a, 4) if a is not None else None}), 'geometry': mapping(rnd(g))})
feats.sort(key=lambda f: -(f['properties']['area_km2'] or -1))
json.dump({'type': 'FeatureCollection', 'name': 'forest_names', 'features': feats}, open(f'{D}/forest_names.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))
print('forest_names', len(feats), 'skipped', skipped)
for f in feats:
    p = f['properties']; print('   ', p['area_km2'], p.get('name'), p.get('landuse'), p.get('natural'), p.get('leisure'), p['osm_id'], f['geometry']['type'])
# keep OSM natural-monument-type areas for protected layer
prot_osm = []
for f in feats:
    p = f['properties']
    if p['osm_id'] in ('way/211578007', 'way/212510589', 'relation/15919589'):
        q = dict(p); q['source'] = 'OpenStreetMap'; q['layer'] = 'osm_named_nature_area'
        if 'source' in p: q['osm_source'] = p['source']
        prot_osm.append({'type': 'Feature', 'properties': q, 'geometry': f['geometry']})
json.dump(prot_osm, open(f'{D}/raw/prot_osm_features.json', 'w'), ensure_ascii=False)
