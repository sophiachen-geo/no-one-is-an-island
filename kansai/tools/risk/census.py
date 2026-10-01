"""2020 census for Shingū (30207) and Kihō (24562) from the e-Stat downloads (fetch.py):
  derived_smallarea_age_2020_shingu_kiho.geojson/.csv — small areas (町丁・字等) with total, 0–14, 15–64, 65+, 75+; areas whose
    figures are suppressed (秘匿, HTKSYORI 2) are merged into the area that receives them (HTKSAKI);
  derived_mesh250_2020_shingu_kiho.geojson — every 250 m cell touching either town: total, 65+, 75+, 85+, households, the share
    of the cell in each town; suppressed cells keep their total and pass their ages to the receiving cell.
Written to the current directory."""
import zipfile, io, csv, json, math, os
import shapefile
import cfg
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union

SA = cfg.dl('census2020_smallarea')
ME = cfg.dl('census2020_mesh')
OUT = os.getcwd()
CITIES = {'30207': ('30', '和歌山県', '新宮市'), '24562': ('24', '三重県', '紀宝町')}

def read_tbl(path):
    z = zipfile.ZipFile(path); n = z.namelist()[0]
    rows = list(csv.reader(io.StringIO(z.read(n).decode('cp932'))))
    return rows[0], rows[1], rows[2:]

def num(x):
    if x == '-':  # e-Stat: '-' = no population (zero)
        return 0
    try: return int(x)
    except: return None

# ---------- small areas ----------
out_rows = []
features = []
for city, (pref, pname, cname) in CITIES.items():
    h, h2, rows = read_tbl(os.path.join(SA, f'tblT001082C{pref}.zip'))
    ix = {k: i for i, k in enumerate(h)}
    data = {r[0]: r for r in rows if r[0].startswith(city)}
    # boundaries
    zf = zipfile.ZipFile(os.path.join(SA, f'A002005212020DDSWC{city}-JGD2011.zip'))
    tmp = os.path.join(OUT, '_census', f'_b{city}_jgd2011'); os.makedirs(tmp, exist_ok=True); zf.extractall(tmp)
    r = shapefile.Reader(os.path.join(tmp, f'r2ka{city}'), encoding='cp932')
    geoms = {}
    for sr in r.iterShapeRecords():
        k = sr.record['KEY_CODE']
        if sr.record['HCODE'] != 8101:  # 8101 = land; 8154 = water etc.
            continue
        geoms.setdefault(k, []).append(shape(sr.shape.__geo_interface__))
    # leaf rows = keys present in boundaries
    groups = {}
    for k in geoms:
        row = data.get(k)
        if row is None:
            print('no table row for', k); continue
        lvl, htk, saki, gas = row[ix['HYOSYO']], row[ix['HTKSYORI']], row[ix['HTKSAKI']], row[ix['GASSAN']]
        # group key: receiving area for hidden areas
        if htk == '2':
            # HTKSAKI is code within city: either 4-digit (oaza) or 6-digit (oaza+chome)
            gk = city + saki
        else:
            gk = k
        rec = dict(KEY_CODE=k, pref=pname, city=cname, name=row[ix['NAME']], hyosyo=lvl, htksyori=htk,
                   htksaki=saki, gassan=gas,
                   pop_total=num(row[ix['T001082001']]), age0_14=num(row[ix['T001082017']]),
                   age15_64=num(row[ix['T001082018']]), age65p=num(row[ix['T001082019']]),
                   age75p=num(row[ix['T001082020']]), group_key=gk)
        g = unary_union(geoms[k])
        # approximate area (km2) using local equirectangular scaling
        lat = g.centroid.y
        rec['area_km2_approx'] = round(g.area * (111.32 ** 2) * math.cos(math.radians(lat)), 4)
        known = [rec['age0_14'], rec['age15_64'], rec['age65p']]
        rec['share65_excl_unknown'] = round(rec['age65p'] / sum(known), 4) if all(v is not None for v in known) and sum(known) > 0 else None
        out_rows.append(rec)
        groups.setdefault(gk, {'geoms': [], 'members': []})
        groups[gk]['geoms'].append(g); groups[gk]['members'].append(rec)
    for gk, gd in groups.items():
        recv = data.get(gk)
        if recv is None:
            # receiving key might be 9-digit oaza code when saki is 4 digits
            print('missing receiving row', gk); continue
        members = gd['members']
        props = dict(group_key=gk, pref=pname, city=cname, name=recv[ix['NAME']],
                     merged_names=';'.join(m['name'] for m in members if m['KEY_CODE'] != gk) or None,
                     pop_total=sum(m['pop_total'] or 0 for m in members),  # hidden members carry X
                     age0_14=num(recv[ix['T001082017']]), age15_64=num(recv[ix['T001082018']]),
                     age65p=num(recv[ix['T001082019']]), age75p=num(recv[ix['T001082020']]))
        props['pop_total'] = num(recv[ix['T001082001']])
        known = [props['age0_14'], props['age15_64'], props['age65p']]
        props['share65_excl_unknown'] = round(props['age65p'] / sum(known), 4) if all(v is not None for v in known) and sum(known) > 0 else None
        geom = unary_union(gd['geoms'])
        features.append({'type': 'Feature', 'properties': props, 'geometry': mapping(geom)})
    # check totals
    tot = sum(f['properties']['pop_total'] for f in features if f['properties']['city'] == cname)
    t65 = sum(f['properties']['age65p'] for f in features if f['properties']['city'] == cname)
    crow = data[city]
    print(cname, 'groups', len(groups), 'sum pop', tot, 'official', crow[ix['T001082001']], 'sum65', t65, 'official65', crow[ix['T001082019']])

with open(os.path.join(OUT, 'derived_smallarea_age_2020_shingu_kiho.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
with open(os.path.join(OUT, 'derived_smallarea_age_2020_shingu_kiho.geojson'), 'w', encoding='utf-8') as f:
    json.dump({'type': 'FeatureCollection',
               'name': 'census2020_smallarea_age_shingu_kiho',
               'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::6668'}},
               'features': features}, f, ensure_ascii=False)

# ---------- municipal polygons (for mesh assignment) ----------
muni = {}
for city in CITIES:
    gs = [shape(f['geometry']) for f in features if f['properties']['group_key'].startswith(city)]
    muni[city] = unary_union(gs)

# ---------- 250 m mesh ----------
def mesh_bounds(code):
    code = str(code)
    lat = int(code[0:2]) / 1.5; lon = int(code[2:4]) + 100
    dlat, dlon = 40 / 60, 1.0
    lat += int(code[4]) * 5 / 60; lon += int(code[5]) * 7.5 / 60; dlat, dlon = 5 / 60, 7.5 / 60
    lat += int(code[6]) * 30 / 3600; lon += int(code[7]) * 45 / 3600; dlat, dlon = 30 / 3600, 45 / 3600
    for d in code[8:]:
        dlat /= 2; dlon /= 2
        d = int(d)
        if d in (3, 4): lat += dlat
        if d in (2, 4): lon += dlon
    return lon, lat, lon + dlon, lat + dlat

def load_mesh(t, unit):
    out = {}
    for c in ('5035', '5036'):
        h, h2, rows = read_tbl(os.path.join(ME, f'tbl{t}{unit}{c}.zip'))
        for r in rows:
            out[r[0]] = dict(zip(h, r))
    return h, h2, out

h, h2, m250 = load_mesh('T001142', 'Q')
h5, h25, m250a = load_mesh('T001196', 'Q')
lab = dict(zip(h, h2))
mfeat = []
summary = {c: {'pop': 0, 'pop_w': 0.0} for c in CITIES}
for code, rec in m250.items():
    b = box(*mesh_bounds(code))
    fr = {c: (b.intersection(muni[c]).area / b.area) for c in CITIES if b.intersects(muni[c])}
    if not fr:
        continue
    def g(k):
        v = rec.get(k); return None if v in (None, '', '*') else int(v)
    a5 = m250a.get(code, {})
    props = dict(mesh250=code, htksyori=rec['HTKSYORI'], htksaki=rec['HTKSAKI'], gassan=rec['GASSAN'],
                 pop_total=g('T001142001'), age0_14=g('T001142004'), age15_64=g('T001142010'),
                 age65p=g('T001142019'), age75p=g('T001142022'), age85p=g('T001142025'),
                 households=g('T001142034'), hh_with_65p=g('T001142047'),
                 hh_elderly_single=g('T001142049'), hh_elderly_couple=g('T001142050'),
                 mean_age=a5.get('T001196064'), median_age=a5.get('T001196065'),
                 frac_in_shingu=round(fr.get('30207', 0), 4), frac_in_kiho=round(fr.get('24562', 0), 4))
    mfeat.append({'type': 'Feature', 'properties': props, 'geometry': mapping(b)})
    for c, f_ in fr.items():
        summary[c]['pop_w'] += (props['pop_total'] or 0) * f_
with open(os.path.join(OUT, 'derived_mesh250_2020_shingu_kiho.geojson'), 'w', encoding='utf-8') as f:
    json.dump({'type': 'FeatureCollection', 'name': 'census2020_mesh250_shingu_kiho',
               'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::6668'}},
               'features': mfeat}, f, ensure_ascii=False)
print('mesh250 cells touching Shingu/Kiho:', len(mfeat))
for c, s in summary.items():
    print(c, 'area-weighted pop from 250m mesh', round(s['pop_w']))
star = sum(1 for f_ in mfeat if f_['properties']['age65p'] is None)
print('cells with suppressed 65+ (*):', star)
print('cells straddling both municipalities:', sum(1 for f_ in mfeat if f_['properties']['frac_in_shingu'] > 0 and f_['properties']['frac_in_kiho'] > 0))
