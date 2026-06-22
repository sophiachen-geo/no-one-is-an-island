// Region + content helpers shared across the browse views.

export const REGIONS = [
  { id: 'setouchi', label: 'Setouchi',  place: 'Japan · Inland Sea', color: '#6fbfa6' },
  { id: 'okinawa',  label: 'Okinawa',   place: 'Japan · Ryukyu',     color: '#5bbcd6' },
  { id: 'matsu',    label: 'Matsu',     place: 'Taiwan',             color: '#8f9ee0' },
  { id: 'hongkong', label: 'Hong Kong', place: 'Hong Kong',          color: '#e8a06a' },
  { id: 'fujian',   label: 'Fujian',    place: 'Mainland China',     color: '#e08aa8' },
];

const PLACE_REGION = {
  naoshima: 'setouchi', shodoshima: 'setouchi', honjima: 'setouchi',
  okinawa: 'okinawa',
  nangan: 'matsu', beigan: 'matsu', dongju: 'matsu', xiju: 'matsu',
  'lantau-muiwo': 'hongkong', 'cheung-chau': 'hongkong', 'sai-kung': 'hongkong',
  'yim-tin-tsai': 'hongkong', lamma: 'hongkong', 'ap-lei-chau': 'hongkong',
  aberdeen: 'hongkong', 'ma-wan': 'hongkong',
  meizhou: 'fujian', gulangyu: 'fujian',
};

export const MOOD_COLOR = {
  sacred: '#d9a05b',
  quiet: '#6fbfa6',
  lyrical: '#5bbcd6',
  conflicted: '#d98a6a',
  ghostly: '#a89bc4',
};

export const regionForPlace = (id) => PLACE_REGION[id] || null;
export const regionMeta = (rid) => REGIONS.find((r) => r.id === rid) || null;

export function placeLabel(id) {
  return id
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function fragmentRegions(frag) {
  return [...new Set(frag.places.map(regionForPlace).filter(Boolean))];
}

// Plain-text preview from markdown body (drops headings + md symbols).
export function plainExcerpt(body, n = 165) {
  const text = body
    .split('\n')
    .filter((l) => !l.trim().startsWith('#'))
    .join(' ')
    .replace(/[*_`#>[\]]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (text.length <= n) return text;
  return text.slice(0, n).replace(/\s+\S*$/, '') + '…';
}

const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Compact "Sep–Nov 2025" style range from a fragment's travel map.
export function travelRange(travel) {
  const entries = Object.values(travel || {});
  if (!entries.length) return null;
  const months = entries
    .map((t) => (t.year && t.month ? t.year * 12 + t.month : null))
    .filter((v) => v != null)
    .sort((a, b) => a - b);
  if (!months.length) return null;
  const fmt = (v) => `${MONTHS[((v - 1) % 12) + 1]} ${Math.floor((v - 1) / 12)}`;
  const lo = fmt(months[0]);
  const hi = fmt(months[months.length - 1]);
  return lo === hi ? lo : `${lo.split(' ')[0]}–${hi}`;
}

// Stories sharing a place or tag with `frag`, ranked by overlap.
export function relatedFragments(frag, all, limit = 4) {
  const places = new Set(frag.places);
  const tags = new Set(frag.tags);
  return all
    .filter((f) => f.slug !== frag.slug)
    .map((f) => {
      const sharedPlaces = f.places.filter((p) => places.has(p));
      const sharedTags = f.tags.filter((t) => tags.has(t));
      return { frag: f, score: sharedPlaces.length * 2 + sharedTags.length, sharedPlaces, sharedTags };
    })
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}
