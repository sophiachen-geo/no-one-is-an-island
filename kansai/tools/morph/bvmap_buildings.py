# Extract building footprints from GSI optimal vector tiles (experimental_bvmap) z16
import mapbox_vector_tile, glob, os, sys, json, math, collections
import numpy as np, shapely
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
D = sys.argv[1]
Z = 16
W, S, E, N = 135.955, 33.655, 136.020, 33.760
LABEL = {3101: '普通建物', 3102: '堅ろう建物', 3103: '高層建物', 3111: '普通無壁舎', 3112: '堅ろう無壁舎'}
pieces = []   # dict(geom, props, tile)
layer_names = collections.Counter(); schema = None; n_feat_raw = 0; n_lines = 0; ext_seen = set()
for f in sorted(glob.glob(f'{D}/raw/bvmap/z16/*.pbf')):
    z, tx, ty = map(int, os.path.basename(f)[:-4].split('_'))
    t = mapbox_vector_tile.decode(open(f, 'rb').read(), default_options={'y_coord_down': True})
    for k in t: layer_names[k] += 1
    lyr = t.get('building')
    if not lyr: continue
    ext = lyr['extent']; ext_seen.add(ext)
    for ft in lyr['features']:
        n_feat_raw += 1
        g = ft['geometry']
        if g['type'] not in ('Polygon', 'MultiPolygon'):
            n_lines += 1; continue
        geom = shape(g)
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        geom = shapely.clip_by_rect(geom, 0, 0, ext, ext)
        if geom.is_empty: continue
        # to global pixel coords (units of 1/ext tile)
        geom = shapely.transform(geom, lambda c: c + np.array([tx * ext, ty * ext], dtype=float))
        for part in shapely.get_parts(geom):
            if part.geom_type == 'Polygon' and part.area > 0:
                pieces.append({'g': part, 'p': ft['properties'], 't': (tx, ty), 'ext': ext})
            elif part.geom_type in ('GeometryCollection', 'MultiPolygon'):
                for q in shapely.get_parts(part):
                    if q.geom_type == 'Polygon' and q.area > 0:
                        pieces.append({'g': q, 'p': ft['properties'], 't': (tx, ty), 'ext': ext})
print('layers seen (tiles):', dict(layer_names))
print('building features raw', n_feat_raw, 'outline lines skipped', n_lines, 'polygon pieces (clipped to tile)', len(pieces), 'extent', ext_seen)
EXT = ext_seen.pop()
# --- union-find across tile edges
parent = list(range(len(pieces)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
def union(i, j):
    ri, rj = find(i), find(j)
    if ri != rj: parent[rj] = ri
def edge_intervals(poly, axis, value, tol=1e-6):
    """intervals along the other axis where polygon boundary lies on line coord[axis]==value"""
    out = []
    for ring in [poly.exterior] + list(poly.interiors):
        c = np.asarray(ring.coords)
        on = np.abs(c[:, axis] - value) < tol
        both = on[:-1] & on[1:]
        for k in np.where(both)[0]:
            a, b = c[k, 1 - axis], c[k + 1, 1 - axis]
            out.append((min(a, b), max(a, b)))
    return out
# index pieces by tile and edge contact
by_edge = collections.defaultdict(list)  # key: ('v', X) or ('h', Y) -> list of (piece idx, side)
for i, pc in enumerate(pieces):
    tx, ty = pc['t']; minx, miny, maxx, maxy = pc['g'].bounds
    x0, y0, x1, y1 = tx * EXT, ty * EXT, (tx + 1) * EXT, (ty + 1) * EXT
    if abs(maxx - x1) < 1e-6: by_edge[('v', x1)].append((i, 0))
    if abs(minx - x0) < 1e-6: by_edge[('v', x0)].append((i, 1))
    if abs(maxy - y1) < 1e-6: by_edge[('h', y1)].append((i, 0))
    if abs(miny - y0) < 1e-6: by_edge[('h', y0)].append((i, 1))
merges = 0
for (kind, val), lst in by_edge.items():
    axis = 0 if kind == 'v' else 1
    A = [(i, edge_intervals(pieces[i]['g'], axis, val)) for i, s in lst if s == 0]
    B = [(j, edge_intervals(pieces[j]['g'], axis, val)) for j, s in lst if s == 1]
    for i, ia in A:
        if not ia: continue
        for j, jb in B:
            if not jb: continue
            ov = 0.0
            for a0, a1 in ia:
                for b0, b1 in jb:
                    ov = max(ov, min(a1, b1) - max(a0, b0))
            if ov > 0.5:   # > 0.5 tile units (~6 cm) of shared edge
                union(i, j); merges += 1
groups = collections.defaultdict(list)
for i in range(len(pieces)): groups[find(i)].append(i)
print('merge links', merges, 'buildings after merge', len(groups))
# --- build output
def px2ll(c):
    n = EXT * 2 ** Z
    lon = c[:, 0] / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * c[:, 1] / n))))
    return np.column_stack([lon, lat])
feats = []; multi = 0; codes = collections.Counter(); prop_conflict = 0
for root, idx in groups.items():
    if len(idx) == 1:
        g = pieces[idx[0]]['g']
    else:
        gs = [pieces[k]['g'] for k in idx]
        base = gs[0]
        gs = [base] + [shapely.snap(x, base, 1.0) for x in gs[1:]]
        g = shapely.union_all(gs)
        if g.geom_type != 'Polygon':
            g2 = g.buffer(0.5, join_style='mitre').buffer(-0.5, join_style='mitre')
            if g2.geom_type == 'Polygon': g = g2
            else: multi += 1
        props_set = {json.dumps(pieces[k]['p'], sort_keys=True) for k in idx}
        if len(props_set) > 1: prop_conflict += 1
    g = shapely.simplify(g, 0.0)  # drop collinear vertices from tile cuts
    g = shapely.transform(g, px2ll)
    g = shapely.transform(g, lambda c: np.round(c, 7))
    if not g.is_valid:
        g = shapely.make_valid(g)
    # area filter: keep inside the requested area (by representative point)
    rp = g.representative_point()
    if not (W <= rp.x <= E and S <= rp.y <= N):
        continue
    p = pieces[idx[0]]['p']
    fc = int(p.get('ftCode')) if p.get('ftCode') is not None else None
    codes[fc] += 1
    props = {'ftCode': fc}
    if p.get('lvOrder') not in (None, 0): props['lvOrder'] = p.get('lvOrder')
    if p.get('orgGILvl') not in (None, '2500'): props['orgGILvl'] = p.get('orgGILvl')
    feats.append((g, props))
print('multipart after merge', multi, 'groups with differing props', prop_conflict)
print('features in area', len(feats), 'codes', dict(codes))
# write compact GeoJSON: 6 decimals (~0.1 m)
def fmt_geom(g):
    m = mapping(shapely.transform(g, lambda c: np.round(c, 6)))
    return m
out = {'type': 'FeatureCollection', 'name': 'buildings',
       'attribution': '出典：国土地理院（地理院タイル／最適化ベクトルタイル experimental_bvmap） https://maps.gsi.go.jp/development/ichiran.html',
       'ftCode_labels': {str(k): v for k, v in LABEL.items()},
       'defaults': {'lvOrder': 0, 'orgGILvl': '2500'},
       'features': [{'type': 'Feature', 'properties': pr, 'geometry': fmt_geom(g)} for g, pr in feats]}
s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open(f'{D}/buildings.geojson', 'w').write(s)
print('size', len(s.encode()))
json.dump({'count': len(feats), 'codes': {str(k): v for k, v in codes.items()}, 'raw_features': n_feat_raw, 'outline_lines_skipped': n_lines,
           'pieces': len(pieces), 'merge_links': merges, 'multipart': multi, 'layers': dict(layer_names), 'extent': EXT}, open(f'{D}/raw/bvmap/stats.json', 'w'), indent=1)
