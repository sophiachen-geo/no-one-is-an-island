export function buildGraph(fragments) {
  const placeMap = new Map();
  const linkMap  = new Map();

  for (const frag of fragments) {
    for (const pid of frag.places) {
      if (!placeMap.has(pid)) {
        placeMap.set(pid, {
          id:        pid,
          label:     pid.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join(' '),
          fragments: [],
          tags:      new Set(),
          coords:    null,
        });
      }
      const node = placeMap.get(pid);
      node.fragments.push(frag);
      frag.tags.forEach(t => node.tags.add(t));
      if (frag.coords && frag.coords[pid]) node.coords = frag.coords[pid];
    }

    // links between every pair of places in this fragment
    const ps = frag.places;
    for (let i = 0; i < ps.length; i++) {
      for (let j = i + 1; j < ps.length; j++) {
        const key = [ps[i], ps[j]].sort().join('|');
        if (!linkMap.has(key)) linkMap.set(key, { source: ps[i], target: ps[j], fragments: [] });
        linkMap.get(key).fragments.push(frag);
      }
    }
  }

  const nodes = Array.from(placeMap.values()).map(n => ({
    ...n,
    tags:   Array.from(n.tags),
    weight: n.fragments.length,
  }));

  const links = Array.from(linkMap.values());

  const allTags = [...new Set(fragments.flatMap(f => f.tags))].sort();

  return { nodes, links, allTags };
}
