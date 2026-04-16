import yaml from 'js-yaml';

export function parseFragment(raw, filepath) {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return null;
  try {
    const meta = yaml.load(match[1]) || {};
    const body = match[2].trim();
    const slug = filepath.replace(/\.md$/, '').split('/').pop();
    return {
      slug,
      title:    meta.title    || slug,
      places:   meta.places   || [],
      tags:     meta.tags     || [],
      mood:     meta.mood     || null,
      subtitle: meta.subtitle || null,
      travel:   meta.travel   || {},
      coords:   meta.coords   || {},
      photo:    meta.photo    || null,
      body,
    };
  } catch (e) {
    console.warn(`parseFragment: failed on ${filepath}`, e);
    return null;
  }
}
