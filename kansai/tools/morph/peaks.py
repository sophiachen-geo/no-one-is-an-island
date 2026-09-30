import json, re, sys, os
D = sys.argv[1]
W, S, E, N = 135.25, 33.38, 136.42, 34.45
js = json.load(open(f'{D}/raw/osm_peaks.json'))
def parse_ele(v):
    if v is None: return None
    s = str(v).strip().replace(',', '.').replace('ｍ', 'm')
    s = re.sub(r'[０-９．]', lambda m: chr(ord(m.group(0)) - 0xFEE0), s)
    m = re.match(r'^~?\s*(-?\d+(?:\.\d+)?)\s*(m|meters|metres|メートル)?\s*$', s, re.I)
    if m: return float(m.group(1))
    m = re.match(r'^(-?\d+(?:\.\d+)?)\s*(ft|feet)$', s, re.I)
    if m: return round(float(m.group(1)) * 0.3048, 1)
    m = re.search(r'(-?\d+(?:\.\d+)?)', s)
    return float(m.group(1)) if m else None
feats = []; unparsed = []; n_unnamed = 0
for e in js['elements']:
    t = e.get('tags', {})
    if not (W <= e['lon'] <= E and S <= e['lat'] <= N): continue
    if 'name' not in t:
        n_unnamed += 1; continue
    ele = parse_ele(t.get('ele'))
    if t.get('ele') is not None and ele is None: unparsed.append((t['name'], t.get('ele')))
    if ele is not None and ele == int(ele): ele = int(ele)
    p = {'name': t['name']}
    if 'name:en' in t: p['name:en'] = t['name:en']
    p['ele'] = ele
    p['osm_id'] = f"node/{e['id']}"
    p['natural'] = t.get('natural')
    for k in ('name:ja-Hira', 'name:ja-Latn', 'alt_name', 'wikidata'):
        if k in t: p[k] = t[k]
    if 'ele' in t and str(t['ele']).strip() != str(ele): p['ele_raw'] = t['ele']
    feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': [round(e['lon'], 6), round(e['lat'], 6)]}})
feats.sort(key=lambda f: -(f['properties']['ele'] or -1))
fc = {'type': 'FeatureCollection', 'name': 'peaks', 'features': feats}
json.dump(fc, open(f'{D}/peaks.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))
print('named peaks', len(feats), 'with ele', sum(1 for f in feats if f['properties']['ele'] is not None), 'unnamed skipped', n_unnamed, 'unparsed', unparsed)
print('size', os.path.getsize(f'{D}/peaks.geojson'))
print('--- top 25 by ele')
for f in feats[:25]:
    p = f['properties']; c = f['geometry']['coordinates']
    print(f"{p['ele']:>6}  {p['name']}  ({p.get('name:en','')})  {c[1]:.4f},{c[0]:.4f}  {p['osm_id']}")
# targets
def norm(s): return re.sub(r'[ヶケがヵノの\s（）()・]', '', s)
targets = ['八経ヶ岳', '釈迦ヶ岳', '大台ヶ原', '日出ヶ岳', '玉置山', '大塔山', '法師山', '烏帽子山', '妙法山', '大雲取山', '子ノ泊山', '千穂ヶ峰', '千穂ヶ峯', '権現山', '神倉山', '護摩壇山', '伯母子岳', '果無山', '冷水山', '八剣山', '仏経ヶ岳', '安堵山', '和田森', 'ブナの森', '石地力山', '鉾尖岳', '黒尾山', '笠捨山', '行仙岳', '弥山', '稲村ヶ岳', '山上ヶ岳', '大普賢岳']
print('--- targets')
for tg in targets:
    hits = [f for f in feats if norm(tg) in norm(f['properties']['name']) or norm(f['properties']['name']) in norm(tg) and len(norm(f['properties']['name'])) >= 2]
    hits = [f for f in hits if norm(tg) in norm(f['properties']['name']) or norm(f['properties']['name']) == norm(tg)]
    print(tg, '->', [(f['properties']['name'], f['properties']['ele'], f['properties']['osm_id'], round(f['geometry']['coordinates'][1],4), round(f['geometry']['coordinates'][0],4)) for f in hits] or 'NOT FOUND')
